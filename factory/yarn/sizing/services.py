"""
Services for Sizing Outcome and Beam Assignment workflow.
Encapsulates transaction-safe business logic, row locking, status transitions,
and audit logging.
"""

import logging
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from factory.beam.models import Beam
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from audit_logs.utils import log_activity

logger = logging.getLogger(__name__)


def assign_beams_to_outcome(outcome=None, beam_ids=None, user=None, request=None, **kwargs):
    """
    Atomically assign a list of existing Beams to a YarnOutcome or SizingOutcome.

    Validates:
      - beam_ids is non-empty
      - No duplicates within beam_ids
      - All Beams exist
      - Physical status:
        * If assigning to SizingOutcome: only Beams with status == SIZING are allowed.
        * If assigning to YarnOutcome: only Beams with status == AVAILABLE are allowed.
      - No Beam has an active sizing assignment in another outcome.
      - The YarnOutcome is valid

    Updates:
      - Attaches Beams to the SizingBeamAssignment
      - Updates each Beam's status to SIZING
      - Emits audit log entry
    """
    sizing_outcome = kwargs.get("sizing_outcome")
    if sizing_outcome is None and isinstance(outcome, SizingOutcome):
        sizing_outcome = outcome

    is_sizing_outcome = kwargs.get("is_sizing_outcome", False) or (sizing_outcome is not None)

    if sizing_outcome:
        yarn_outcome = getattr(sizing_outcome, "yarn_outcome", None)
        if not yarn_outcome and hasattr(sizing_outcome, "sizing") and sizing_outcome.sizing:
            yo = sizing_outcome.sizing.yarn_outcomes.filter(outcome_type="Sizing").first()
            if not yo:
                from django.utils import timezone
                from factory.yarn.yarn_intake.models import YarnIntake, Supplier, YarnOutcome
                intake = YarnIntake.objects.first()
                if not intake:
                    supplier = Supplier.objects.first()
                    if not supplier:
                        supplier = Supplier.objects.create(supplier_name="Auto Supplier", status="Active")
                    intake = YarnIntake.objects.create(
                        yarn_name="Default Intake",
                        supplier=supplier,
                        bags=0,
                        cones_per_bag=0,
                        weight_per_bag_kg=0,
                        rate_per_bag=0,
                        intake_date=getattr(sizing_outcome, "outcome_date", None) or timezone.now().date(),
                    )
                yo = YarnOutcome.objects.create(
                    yarn_intake=intake,
                    outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
                    sizing=sizing_outcome.sizing,
                    outcome_bags=0,
                    outcome_weight_per_bag_kg=0,
                    outcome_date=getattr(sizing_outcome, "outcome_date", None) or timezone.now().date(),
                    notes=f"Auto-created for Sizing Outcome #{sizing_outcome.id}",
                )
            yarn_outcome = yo
    else:
        yarn_outcome = outcome or kwargs.get("yarn_outcome")
        if yarn_outcome and hasattr(yarn_outcome, "sizing") and not hasattr(yarn_outcome, "yarn_intake"):
            sizing_outcome = yarn_outcome
            is_sizing_outcome = True
            yo = getattr(sizing_outcome, "yarn_outcome", None)
            if not yo and sizing_outcome.sizing:
                yo = sizing_outcome.sizing.yarn_outcomes.filter(outcome_type="Sizing").first()
            yarn_outcome = yo

    if not beam_ids:
        raise ValidationError({"beam_ids": ["At least one beam ID must be provided."]})

    # Check for duplicates in the submitted list
    seen = set()
    duplicates = set()
    for bid in beam_ids:
        if bid in seen:
            duplicates.add(bid)
        seen.add(bid)
    if duplicates:
        raise ValidationError({
            "beam_ids": [f"Duplicate beam IDs submitted: {sorted(list(duplicates))}."]
        })

    try:
        with transaction.atomic():
            # Lock the target Beam rows using select_for_update to avoid concurrency race conditions
            locked_beams = list(
                Beam.objects.select_for_update().filter(id__in=beam_ids)
            )

            # Check that all requested Beams exist
            found_ids = {b.id for b in locked_beams}
            missing_ids = set(beam_ids) - found_ids
            if missing_ids:
                raise ValidationError({
                    "beam_ids": [f"Beam with ID {mid} does not exist." for mid in sorted(list(missing_ids))]
                })

            # Preserve the order of beam_ids as requested
            beam_map = {b.id: b for b in locked_beams}
            ordered_beams = [beam_map[bid] for bid in beam_ids]

            expected_status = (
                kwargs.get("allowed_status")
                or (Beam.StatusChoices.SIZING if is_sizing_outcome else Beam.StatusChoices.AVAILABLE)
            )

            # Validate each beam's physical status and existing active assignments
            for beam in ordered_beams:
                if beam.status != expected_status:
                    raise ValidationError({
                        "beam_ids": [
                            f"Beam '{beam.beam_number}' cannot be assigned because its status is "
                            f"'{beam.status}'. Only '{expected_status}' beams can be assigned."
                        ]
                    })

                # Check if beam already has an active assignment in another outcome
                active_assignment = SizingBeamAssignment.objects.filter(
                    beam=beam,
                    status__in=[
                        SizingBeamAssignment.StatusChoices.ASSIGNED,
                        SizingBeamAssignment.StatusChoices.IN_USE,
                        SizingBeamAssignment.StatusChoices.RECEIVED,
                    ],
                ).first()

                if active_assignment:
                    # If this is sizing outcome and the active assignment belongs to this same yarn_outcome
                    # and is currently waiting to be received (ASSIGNED or IN_USE):
                    if (
                        is_sizing_outcome
                        and yarn_outcome
                        and active_assignment.yarn_outcome_id == yarn_outcome.id
                        and active_assignment.status in [
                            SizingBeamAssignment.StatusChoices.ASSIGNED,
                            SizingBeamAssignment.StatusChoices.IN_USE,
                        ]
                    ):
                        pass
                    else:
                        raise ValidationError({
                            "beam_ids": [
                                f"Beam '{beam.beam_number}' already has an active sizing assignment "
                                f"(Assignment #{active_assignment.id} in Outcome #{active_assignment.yarn_outcome_id})."
                            ]
                        })

            target_status = (
                SizingBeamAssignment.StatusChoices.RECEIVED
                if is_sizing_outcome
                else SizingBeamAssignment.StatusChoices.ASSIGNED
            )

            # Check if an active/matching SizingBeamAssignment already exists for this outcome, else create one
            assignment = SizingBeamAssignment.objects.filter(
                yarn_outcome=yarn_outcome,
                status__in=[
                    SizingBeamAssignment.StatusChoices.ASSIGNED,
                    SizingBeamAssignment.StatusChoices.IN_USE,
                    SizingBeamAssignment.StatusChoices.RECEIVED,
                ],
            ).first()
            if not assignment:
                assignment = SizingBeamAssignment.objects.create(
                    yarn_outcome=yarn_outcome,
                    status=target_status,
                    created_by=user,
                    updated_by=user,
                )
            else:
                if is_sizing_outcome and assignment.status != target_status:
                    assignment.status = target_status
                    assignment.updated_by = user
                    assignment.save(update_fields=["status", "updated_by", "updated_at"])

            assignment.beam.add(*ordered_beams)

            for beam in ordered_beams:
                beam.status = Beam.StatusChoices.SIZING
                beam.updated_by = user
                beam.save(update_fields=["status", "updated_by", "updated_at"])

            created_assignments = [assignment]

            # Audit log
            beam_numbers = ", ".join(b.beam_number for b in ordered_beams)
            sizing_unit = getattr(yarn_outcome, "sizing", None) if yarn_outcome else None
            sizing_name = sizing_unit.sizing_name if sizing_unit else "N/A"
            action_name = "Receive Beams from Sizing Outcome" if is_sizing_outcome else "Assign Beams to Sizing Outcome"
            log_activity(
                request=request,
                action=action_name,
                description=(
                    f"Recorded {len(ordered_beams)} beam(s) [{beam_numbers}] in "
                    f"Outcome #{getattr(yarn_outcome, 'id', '')} (Sizing: {sizing_name}) with status '{target_status}'."
                ),
                module="Yarn – Sizing",
                status="Success",
                user=user,
            )

            return created_assignments

    except IntegrityError as exc:
        logger.error(f"IntegrityError during beam assignment: {exc}")
        raise ValidationError({
            "beam_ids": ["One or more beams already have an active sizing assignment."]
        })


def create_sizing_outcome(yarn_outcome=None, outcome_date=None, remarks="", beam_ids=None, user=None, request=None, **extra_fields):
    """
    Creates a new SizingOutcome and optionally assigns a batch of Beams atomically.
    Supports either yarn_outcome (preferred) or legacy sizing reference.
    """
    sizing = extra_fields.pop("sizing", None)
    if not yarn_outcome and sizing:
        from factory.yarn.yarn_intake.models import YarnIntake, Supplier, YarnOutcome
        from django.utils import timezone
        yarn_outcome = YarnOutcome.objects.filter(sizing=sizing, outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING).first()
        if not yarn_outcome:
            intake = YarnIntake.objects.first()
            if not intake:
                supplier = Supplier.objects.first()
                if not supplier:
                    supplier = Supplier.objects.create(supplier_name="Auto Supplier", status="Active")
                intake = YarnIntake.objects.create(
                    yarn_name="Default Intake",
                    supplier=supplier,
                    bags=0,
                    cones_per_bag=0,
                    weight_per_bag_kg=0,
                    rate_per_bag=0,
                    intake_date=outcome_date or timezone.now().date(),
                )
            yarn_outcome = YarnOutcome.objects.create(
                yarn_intake=intake,
                outcome_type=YarnOutcome.OutcomeTypeChoices.SIZING,
                sizing=sizing,
                outcome_bags=0,
                outcome_weight_per_bag_kg=0,
                outcome_date=outcome_date or timezone.now().date(),
            )

    with transaction.atomic():
        outcome = SizingOutcome.objects.create(
            yarn_outcome=yarn_outcome,
            outcome_date=outcome_date,
            remarks=remarks or "",
            created_by=user,
            updated_by=user,
            **extra_fields,
        )

        assignments = []
        if beam_ids:
            assignments = assign_beams_to_outcome(
                sizing_outcome=outcome,
                beam_ids=beam_ids,
                user=user,
                request=request,
            )

        sizing_title = (
            yarn_outcome.sizing.sizing_name
            if yarn_outcome and hasattr(yarn_outcome, "sizing") and yarn_outcome.sizing
            else (sizing.sizing_name if sizing else "N/A")
        )
        log_activity(
            request=request,
            action="Create Sizing Outcome",
            description=(
                f"Created Sizing Outcome #{outcome.id} for sizing '{sizing_title}' "
                f"with {len(assignments)} initial beam assignment(s)."
            ),
            module="Yarn – Sizing",
            status="Success",
            user=user,
        )

        return outcome


def transition_beam_assignment(assignment, new_status, user=None, request=None):
    """
    Transition a SizingBeamAssignment to a new status according to the valid workflow:
      ASSIGNED -> IN_USE, COMPLETED, RELEASED
      IN_USE   -> COMPLETED, RELEASED
      COMPLETED -> RELEASED
      RELEASED  -> Terminal (no further transitions)

    Synchronizes physical Beam status:
      - RELEASED: sets released_at = now(), beam.status = AVAILABLE
      - IN_USE: if beam is SIZING, sets beam.status = LOADED
      - COMPLETED: sets beam.status = COMPLETED
    """
    valid_transitions = {
        SizingBeamAssignment.StatusChoices.ASSIGNED: [
            SizingBeamAssignment.StatusChoices.IN_USE,
            SizingBeamAssignment.StatusChoices.RECEIVED,
            SizingBeamAssignment.StatusChoices.COMPLETED,
            SizingBeamAssignment.StatusChoices.RELEASED,
        ],
        SizingBeamAssignment.StatusChoices.IN_USE: [
            SizingBeamAssignment.StatusChoices.RECEIVED,
            SizingBeamAssignment.StatusChoices.COMPLETED,
            SizingBeamAssignment.StatusChoices.RELEASED,
        ],
        SizingBeamAssignment.StatusChoices.RECEIVED: [
            SizingBeamAssignment.StatusChoices.IN_USE,
            SizingBeamAssignment.StatusChoices.COMPLETED,
            SizingBeamAssignment.StatusChoices.RELEASED,
        ],
        SizingBeamAssignment.StatusChoices.COMPLETED: [
            SizingBeamAssignment.StatusChoices.RELEASED,
        ],
        SizingBeamAssignment.StatusChoices.RELEASED: [],
    }

    with transaction.atomic():
        assignment = (
            SizingBeamAssignment.objects
            .select_for_update()
            .get(id=assignment.id if hasattr(assignment, "id") else assignment)
        )
        beam_ids = list(assignment.beam.values_list("id", flat=True))
        beams = list(Beam.objects.select_for_update().filter(id__in=beam_ids))

        if new_status == assignment.status:
            return assignment

        allowed = valid_transitions.get(assignment.status, [])
        if new_status not in allowed:
            raise ValidationError({
                "status": [
                    f"Cannot transition assignment from '{assignment.status}' to '{new_status}'. "
                    f"Allowed transitions: {allowed}."
                ]
            })

        old_status = assignment.status
        assignment.status = new_status
        assignment.updated_by = user

        for beam in beams:
            if new_status == SizingBeamAssignment.StatusChoices.RELEASED:
                beam.status = Beam.StatusChoices.AVAILABLE
            elif new_status == SizingBeamAssignment.StatusChoices.IN_USE:
                if beam.status == Beam.StatusChoices.SIZING:
                    beam.status = Beam.StatusChoices.LOADED
            elif new_status == SizingBeamAssignment.StatusChoices.RECEIVED:
                beam.status = Beam.StatusChoices.SIZING
            elif new_status == SizingBeamAssignment.StatusChoices.COMPLETED:
                beam.status = Beam.StatusChoices.COMPLETED

            beam.updated_by = user
            beam.save(update_fields=["status", "updated_by", "updated_at"])

        if new_status == SizingBeamAssignment.StatusChoices.RELEASED:
            assignment.released_at = timezone.now()

        assignment.save(update_fields=["status", "released_at", "updated_by", "updated_at"])

        beam_numbers = ", ".join(b.beam_number for b in beams)
        log_activity(
            request=request,
            action="Transition Beam Assignment",
            description=(
                f"Transitioned Assignment #{assignment.id} for Beam(s) [{beam_numbers}] "
                f"from '{old_status}' to '{new_status}'."
            ),
            module="Factory – Beams",
            status="Success",
            user=user,
        )

        return assignment


def release_beam_assignment(assignment, user=None, request=None):
    """
    Release a specific SizingBeamAssignment.
    Marks assignment as RELEASED, records released_at, sets Beam back to AVAILABLE.
    Preserves all historical records.
    """
    assignment_obj = (
        assignment if hasattr(assignment, "status")
        else SizingBeamAssignment.objects.get(id=assignment)
    )
    if assignment_obj.status == SizingBeamAssignment.StatusChoices.RELEASED:
        raise ValidationError({
            "detail": f"Assignment #{assignment_obj.id} is already released."
        })

    return transition_beam_assignment(
        assignment=assignment_obj,
        new_status=SizingBeamAssignment.StatusChoices.RELEASED,
        user=user,
        request=request,
    )


def release_beam_active_assignment(beam_or_id, user=None, request=None):
    """
    Finds the active or unreleased sizing assignment for a Beam and releases it.
    """
    beam_id = beam_or_id.id if hasattr(beam_or_id, "id") else beam_or_id
    beam = Beam.objects.get(id=beam_id)

    assignment = (
        SizingBeamAssignment.objects
        .filter(beam=beam_id)
        .exclude(status=SizingBeamAssignment.StatusChoices.RELEASED)
        .order_by("-assigned_at", "-id")
        .first()
    )

    if not assignment:
        raise ValidationError({
            "detail": f"Beam '{beam.beam_number}' has no active or unreleased sizing assignment to release."
        })

    return release_beam_assignment(
        assignment=assignment,
        user=user,
        request=request,
    )


def get_beam_sizing_history(beam_id):
    """
    Retrieves the complete sizing history for a Beam.
    Uses select_related for optimal database query performance.
    """
    return (
        SizingBeamAssignment.objects
        .filter(beam=beam_id)
        .select_related(
            "yarn_outcome",
            "yarn_outcome__sizing",
            "yarn_outcome__yarn_intake",
            "created_by",
            "updated_by",
        )
        .prefetch_related("beam")
        .order_by("-assigned_at", "-id")
    )


def get_beam_active_assignment(beam_id):
    """
    Retrieves the currently active (ASSIGNED, IN_USE, or RECEIVED) sizing assignment for a Beam.
    """
    return (
        SizingBeamAssignment.objects
        .filter(
            beam=beam_id,
            status__in=[
                SizingBeamAssignment.StatusChoices.ASSIGNED,
                SizingBeamAssignment.StatusChoices.IN_USE,
                SizingBeamAssignment.StatusChoices.RECEIVED,
            ],
        )
        .select_related(
            "yarn_outcome",
            "yarn_outcome__sizing",
            "yarn_outcome__yarn_intake",
            "created_by",
            "updated_by",
        )
        .prefetch_related("beam")
        .first()
    )
