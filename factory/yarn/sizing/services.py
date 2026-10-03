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


def assign_beams_to_outcome(sizing_outcome, beam_ids, user=None, request=None):
    """
    Atomically assign a list of existing Beams to a SizingOutcome.

    Validates:
      - beam_ids is non-empty
      - No duplicates within beam_ids
      - All Beams exist
      - All Beams have status == AVAILABLE
      - No Beam has an active (ASSIGNED or IN_USE) sizing assignment
      - The SizingOutcome is valid

    Updates:
      - Creates a SizingBeamAssignment for each Beam
      - Updates each Beam's status to SIZING
      - Emits audit log entry
    """
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

            # Validate each beam's physical status and existing active assignments
            for beam in ordered_beams:
                if beam.status != Beam.StatusChoices.AVAILABLE:
                    raise ValidationError({
                        "beam_ids": [
                            f"Beam '{beam.beam_number}' cannot be assigned because its status is "
                            f"'{beam.status}'. Only 'Available' beams can be assigned."
                        ]
                    })

                # Check if beam already has an active assignment in the DB
                active_assignment = SizingBeamAssignment.objects.filter(
                    beam=beam,
                    status__in=[
                        SizingBeamAssignment.StatusChoices.ASSIGNED,
                        SizingBeamAssignment.StatusChoices.IN_USE,
                    ]
                ).first()
                if active_assignment:
                    raise ValidationError({
                        "beam_ids": [
                            f"Beam '{beam.beam_number}' already has an active sizing assignment "
                            f"(Assignment #{active_assignment.id} in Outcome #{active_assignment.sizing_outcome_id})."
                        ]
                    })

            # Create assignment records and transition beam status to SIZING
            created_assignments = []
            for beam in ordered_beams:
                assignment = SizingBeamAssignment.objects.create(
                    sizing_outcome=sizing_outcome,
                    beam=beam,
                    status=SizingBeamAssignment.StatusChoices.ASSIGNED,
                    created_by=user,
                    updated_by=user,
                )
                beam.status = Beam.StatusChoices.SIZING
                beam.updated_by = user
                beam.save(update_fields=["status", "updated_by", "updated_at"])
                created_assignments.append(assignment)

            # Audit log
            beam_numbers = ", ".join(b.beam_number for b in ordered_beams)
            log_activity(
                request=request,
                action="Assign Beams to Sizing Outcome",
                description=(
                    f"Assigned {len(ordered_beams)} beam(s) [{beam_numbers}] to "
                    f"Sizing Outcome #{sizing_outcome.id} (Sizing: {sizing_outcome.sizing.sizing_name})."
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


def create_sizing_outcome(sizing, outcome_date, remarks="", beam_ids=None, user=None, request=None, **extra_fields):
    """
    Creates a new SizingOutcome and optionally assigns a batch of Beams atomically.
    """
    with transaction.atomic():
        outcome = SizingOutcome.objects.create(
            sizing=sizing,
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

        log_activity(
            request=request,
            action="Create Sizing Outcome",
            description=(
                f"Created Sizing Outcome #{outcome.id} for sizing '{sizing.sizing_name}' "
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
            SizingBeamAssignment.StatusChoices.COMPLETED,
            SizingBeamAssignment.StatusChoices.RELEASED,
        ],
        SizingBeamAssignment.StatusChoices.IN_USE: [
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
            .select_related("beam", "sizing_outcome", "sizing_outcome__sizing")
            .get(id=assignment.id if hasattr(assignment, "id") else assignment)
        )
        beam = Beam.objects.select_for_update().get(id=assignment.beam_id)

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

        if new_status == SizingBeamAssignment.StatusChoices.RELEASED:
            assignment.released_at = timezone.now()
            beam.status = Beam.StatusChoices.AVAILABLE
        elif new_status == SizingBeamAssignment.StatusChoices.IN_USE:
            if beam.status == Beam.StatusChoices.SIZING:
                beam.status = Beam.StatusChoices.LOADED
        elif new_status == SizingBeamAssignment.StatusChoices.COMPLETED:
            beam.status = Beam.StatusChoices.COMPLETED

        beam.updated_by = user
        beam.save(update_fields=["status", "updated_by", "updated_at"])
        assignment.save(update_fields=["status", "released_at", "updated_by", "updated_at"])

        log_activity(
            request=request,
            action="Transition Beam Assignment",
            description=(
                f"Transitioned Assignment #{assignment.id} for Beam '{beam.beam_number}' "
                f"from '{old_status}' to '{new_status}' (Beam status: {beam.status})."
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
        .filter(beam_id=beam_id)
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
    Uses select_related and prefetch_related for optimal database query performance.
    """
    return (
        SizingBeamAssignment.objects
        .filter(beam_id=beam_id)
        .select_related(
            "sizing_outcome",
            "sizing_outcome__sizing",
            "sizing_outcome__created_by",
            "sizing_outcome__updated_by",
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "sizing_outcome__sizing__yarn_outcomes",
            "sizing_outcome__sizing__yarn_outcomes__yarn_intake",
        )
        .order_by("-assigned_at", "-id")
    )


def get_beam_active_assignment(beam_id):
    """
    Retrieves the currently active (ASSIGNED or IN_USE) sizing assignment for a Beam.
    """
    return (
        SizingBeamAssignment.objects
        .filter(
            beam_id=beam_id,
            status__in=[
                SizingBeamAssignment.StatusChoices.ASSIGNED,
                SizingBeamAssignment.StatusChoices.IN_USE,
            ],
        )
        .select_related(
            "sizing_outcome",
            "sizing_outcome__sizing",
            "created_by",
            "updated_by",
        )
        .first()
    )
