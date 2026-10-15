"""
Services for Beam Loading and Production workflow.
Encapsulates transaction safety, select_for_update locking, status transitions,
and audit logging.
"""

import logging
from decimal import Decimal
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from factory.beam.models import Beam, BeamLoading, Production
from factory.loom.models import Loom
from factory.yarn.sizing.models import SizingOutcome
from audit_logs.utils import log_activity

logger = logging.getLogger(__name__)


def load_beam_onto_loom(
    sizing_outcome,
    beam_or_id,
    loom_or_id,
    warp_count="",
    weft_count="",
    cloth_quality="",
    cloth_name=None,
    cloth_name_or_id=None,
    reed_width=None,
    pick=None,
    reed_count=None,
    pick_count=None,
    shortage=None,
    width=None,
    lakhai=None,
    installation_date=None,
    user=None,
    request=None,
    **kwargs,
):
    """
    Atomically loads a returned Sizing Outcome Set onto an existing physical Beam
    and mounts that Beam onto a Loom.

    Rules:
      1. Locks Beam with select_for_update().
      2. Validates Beam.status == AVAILABLE.
      3. Validates Loom exists and is not Inactive or Breakdown.
      4. Validates Beam does not already have an active loading.
      5. Validates Loom does not already have an active loading.
      6. Creates BeamLoading record.
      7. Updates Beam.status = IN_PRODUCTION.
      8. Updates Loom.status = PRODUCTION.
      9. Saves everything inside transaction.atomic().
    """
    beam_id = beam_or_id.id if hasattr(beam_or_id, "id") else beam_or_id
    loom_id = loom_or_id.id if hasattr(loom_or_id, "id") else loom_or_id
    outcome_id = sizing_outcome.id if hasattr(sizing_outcome, "id") else sizing_outcome

    try:
        with transaction.atomic():
            # Lock the beam row
            try:
                beam = Beam.objects.select_for_update().get(id=beam_id)
            except Beam.DoesNotExist:
                raise ValidationError({"beam": [f"Beam with ID {beam_id} does not exist."]})

            # Lock the loom row
            try:
                loom = Loom.objects.select_for_update().get(id=loom_id)
            except Loom.DoesNotExist:
                raise ValidationError({"loom": [f"Loom with ID {loom_id} does not exist."]})

            # Ensure SizingOutcome exists
            if not isinstance(sizing_outcome, SizingOutcome):
                try:
                    sizing_outcome = SizingOutcome.objects.get(id=outcome_id)
                except SizingOutcome.DoesNotExist:
                    raise ValidationError({"sizing_outcome": [f"Sizing outcome with ID {outcome_id} does not exist."]})

            # Check Beam availability: only beams with status LOADED (received from sizing) can be loaded onto loom
            if beam.status != Beam.StatusChoices.LOADED:
                raise ValidationError({
                    "beam": [
                        f"Beam '{beam.beam_number}' cannot be loaded because its status is '{beam.status}'. "
                        f"Only 'Loaded' beams can be loaded."
                    ]
                })

            # Check Loom status
            if loom.status in [Loom.StatusChoices.INACTIVE, Loom.StatusChoices.BREAKDOWN]:
                raise ValidationError({
                    "loom": [
                        f"Loom '{loom.loom_code}' is currently '{loom.status}' and cannot receive a beam."
                    ]
                })

            # Check active loading on Beam
            active_beam_loading = BeamLoading.objects.filter(
                beam=beam,
                status__in=[
                    BeamLoading.StatusChoices.LOADED,
                    BeamLoading.StatusChoices.IN_PRODUCTION,
                ]
            ).first()
            if active_beam_loading:
                raise ValidationError({
                    "beam": [
                        f"Beam '{beam.beam_number}' already has an active loading (Loading #{active_beam_loading.id} on Loom '{active_beam_loading.loom.loom_code}')."
                    ]
                })

            # Check active loading on Loom
            active_loom_loading = BeamLoading.objects.filter(
                loom=loom,
                status__in=[
                    BeamLoading.StatusChoices.LOADED,
                    BeamLoading.StatusChoices.IN_PRODUCTION,
                ]
            ).first()
            if active_loom_loading:
                raise ValidationError({
                    "loom": [
                        f"Loom '{loom.loom_code}' already has an active beam mounted on it "
                        f"(Beam '{active_loom_loading.beam.beam_number}', Loading #{active_loom_loading.id})."
                    ]
                })

            # Resolve cloth_quality and cloth_name
            from factory.cloth.models import ClothName
            resolved_cloth_name = None
            target_cn_id = cloth_name_or_id or cloth_name
            if target_cn_id:
                if isinstance(target_cn_id, ClothName):
                    resolved_cloth_name = target_cn_id
                else:
                    try:
                        resolved_cloth_name = ClothName.objects.get(id=target_cn_id)
                    except (ClothName.DoesNotExist, ValueError):
                        pass

            resolved_quality = str(cloth_quality or "").strip()
            if not resolved_quality and resolved_cloth_name:
                resolved_quality = resolved_cloth_name.name
            elif not resolved_quality:
                parts = []
                rc = int(float(reed_count)) if reed_count else None
                pc = int(float(pick_count or pick)) if (pick_count or pick) else None
                if rc and pc:
                    parts.append(f"{rc}x{pc}")
                wc = str(warp_count or getattr(beam, "warp_count", "") or "").strip()
                wec = str(weft_count or "").strip()
                if wc or wec:
                    parts.append(f"{wc or '40/1'}x{wec or '40/1'}")
                w = int(float(width or getattr(beam, "width", None) or 63))
                resolved_quality = f"{' / '.join(parts)} ({w}\")" if parts else "Cotton Standard 40/40"

            if not resolved_cloth_name and resolved_quality:
                resolved_cloth_name, _ = ClothName.objects.get_or_create(
                    name=resolved_quality,
                    defaults={"created_by": user}
                )

            # Create BeamLoading record
            loading = BeamLoading.objects.create(
                sizing_outcome=sizing_outcome,
                beam=beam,
                loom=loom,
                warp_count=warp_count or getattr(beam, "warp_count", "") or "",
                weft_count=weft_count or "",
                cloth_quality=resolved_quality,
                cloth_name=resolved_cloth_name,
                reed_width=reed_width,
                pick=pick,
                reed_count=reed_count,
                pick_count=pick_count,
                shortage=shortage,
                width=width or getattr(beam, "width", None),
                lakhai=lakhai,
                installation_date=installation_date,
                status=BeamLoading.StatusChoices.LOADED,
                created_by=user,
                updated_by=user,
            )

            # Update Beam and Loom statuses
            beam.status = Beam.StatusChoices.IN_PRODUCTION
            beam.updated_by = user
            beam.save(update_fields=["status", "updated_by", "updated_at"])

            loom.status = Loom.StatusChoices.PRODUCTION
            loom.updated_by = user
            loom.save(update_fields=["status", "updated_by", "updated_at"])

            # Audit log
            log_activity(
                request=request,
                action="Load Beam",
                description=(
                    f"Loaded Beam '{beam.beam_number}' onto Loom '{loom.loom_code}' "
                    f"for Sizing Outcome #{sizing_outcome.id} (Set #{sizing_outcome.set_no})."
                ),
                module="Factory – Beam Loading",
                status="Success",
                user=user,
            )

            return loading

    except IntegrityError as exc:
        logger.error(f"IntegrityError during beam loading: {exc}")
        raise ValidationError({
            "non_field_errors": ["The beam or loom already has an active loading assignment."]
        })


def record_production_entry(
    beam_loading_or_id,
    production_date,
    meters_produced,
    shift="General",
    operator_name="",
    remarks="",
    beam_emptied=False,
    user=None,
    request=None,
):
    """
    Records daily/shift production against a loaded Beam on a Loom.
    If beam_emptied is True:
      - Sets BeamLoading.status = EMPTY
      - Sets Beam.status = AVAILABLE (ready for reuse in next sizing set!)
      - Sets Loom.status = ACTIVE (loom freed for new beam)
      - Preserves historical BeamLoading and Production records
    """
    loading_id = beam_loading_or_id.id if hasattr(beam_loading_or_id, "id") else beam_loading_or_id

    with transaction.atomic():
        try:
            loading = (
                BeamLoading.objects
                .select_for_update()
                .select_related("beam", "loom", "sizing_outcome")
                .get(id=loading_id)
            )
        except BeamLoading.DoesNotExist:
            raise ValidationError({"beam_loading": [f"BeamLoading #{loading_id} does not exist."]})

        beam = Beam.objects.select_for_update().get(id=loading.beam_id)
        loom = Loom.objects.select_for_update().get(id=loading.loom_id)

        # Transition to IN_PRODUCTION if currently LOADED
        if loading.status == BeamLoading.StatusChoices.LOADED:
            loading.status = BeamLoading.StatusChoices.IN_PRODUCTION
            beam.status = Beam.StatusChoices.IN_PRODUCTION
            beam.updated_by = user
            beam.save(update_fields=["status", "updated_by", "updated_at"])

        # Create Production entry
        production = Production.objects.create(
            beam_loading=loading,
            production_date=production_date,
            shift=shift or "General",
            meters_produced=Decimal(str(meters_produced)),
            operator_name=operator_name or "",
            remarks=remarks or "",
            beam_emptied=beam_emptied,
            created_by=user,
            updated_by=user,
        )

        # If beam is empty, release beam and loom
        if beam_emptied:
            loading.status = BeamLoading.StatusChoices.COMPLETED
            loading.updated_by = user
            loading.save(update_fields=["status", "updated_by", "updated_at"])

            beam.status = Beam.StatusChoices.AVAILABLE
            beam.updated_by = user
            beam.save(update_fields=["status", "updated_by", "updated_at"])

            loom.status = Loom.StatusChoices.ACTIVE
            loom.updated_by = user
            loom.save(update_fields=["status", "updated_by", "updated_at"])

            # Release any active SizingBeamAssignment for this beam so it can be reassigned to new sizing cycles
            from factory.yarn.sizing.models import SizingBeamAssignment
            active_sba_list = SizingBeamAssignment.objects.filter(
                beam=beam
            ).exclude(status=SizingBeamAssignment.StatusChoices.RELEASED)
            for sba in active_sba_list:
                sba.status = SizingBeamAssignment.StatusChoices.RELEASED
                sba.released_at = timezone.now()
                sba.updated_by = user
                sba.save(update_fields=["status", "released_at", "updated_by", "updated_at"])
        else:
            loading.updated_by = user
            loading.save(update_fields=["status", "updated_by", "updated_at"])

        log_activity(
            request=request,
            action="Record Production",
            description=(
                f"Logged {meters_produced}m production for Loom '{loom.loom_code}' / Beam '{beam.beam_number}'"
                f" (Empty: {beam_emptied})."
            ),
            module="Factory – Production",
            status="Success",
            user=user,
        )

        return production


def mark_beam_empty_and_available(beam_loading_or_id, user=None, request=None):
    """
    Manually marks a BeamLoading as Empty:
      - Sets Beam.status = AVAILABLE (ready for reuse)
      - Sets Loom.status = ACTIVE
      - Sets BeamLoading.status = EMPTY
      - All history preserved
    """
    loading_id = beam_loading_or_id.id if hasattr(beam_loading_or_id, "id") else beam_loading_or_id

    with transaction.atomic():
        try:
            loading = (
                BeamLoading.objects
                .select_for_update()
                .select_related("beam", "loom")
                .get(id=loading_id)
            )
        except BeamLoading.DoesNotExist:
            raise ValidationError({"detail": f"BeamLoading #{loading_id} does not exist."})

        if loading.status == BeamLoading.StatusChoices.COMPLETED:
            raise ValidationError({"detail": f"BeamLoading #{loading_id} is already marked completed."})

        beam = Beam.objects.select_for_update().get(id=loading.beam_id)
        loom = Loom.objects.select_for_update().get(id=loading.loom_id)

        loading.status = BeamLoading.StatusChoices.COMPLETED
        loading.updated_by = user
        loading.save(update_fields=["status", "updated_by", "updated_at"])


        beam.status = Beam.StatusChoices.AVAILABLE
        beam.updated_by = user
        beam.save(update_fields=["status", "updated_by", "updated_at"])

        loom.status = Loom.StatusChoices.ACTIVE
        loom.updated_by = user
        loom.save(update_fields=["status", "updated_by", "updated_at"])

        # Release any active SizingBeamAssignment for this beam so it can be reassigned to new sizing cycles
        from factory.yarn.sizing.models import SizingBeamAssignment
        active_sba_list = SizingBeamAssignment.objects.filter(
            beam=beam
        ).exclude(status=SizingBeamAssignment.StatusChoices.RELEASED)
        for sba in active_sba_list:
            sba.status = SizingBeamAssignment.StatusChoices.RELEASED
            sba.released_at = timezone.now()
            sba.updated_by = user
            sba.save(update_fields=["status", "released_at", "updated_by", "updated_at"])

        log_activity(
            request=request,
            action="Beam Emptied",
            description=f"Marked Beam '{beam.beam_number}' on Loom '{loom.loom_code}' as empty and Available.",
            module="Factory – Beam Loading",
            status="Success",
            user=user,
        )

        return loading


def get_beam_loading_history(beam_id):
    """
    Returns complete chronological BeamLoading history for a physical Beam,
    showing all sizing sets and looms it was mounted on.
    """
    return (
        BeamLoading.objects
        .filter(beam_id=beam_id)
        .select_related(
            "sizing_outcome",
            "sizing_outcome__yarn_outcome",
            "sizing_outcome__yarn_outcome__sizing",
            "loom",
            "created_by",
            "updated_by",
        )
        .prefetch_related("productions")
        .order_by("-installation_date", "-id")
    )


def calculate_expected_cloth_length(beam_loading):
    """
    Calculates expected cloth production length for a BeamLoading cycle:
    1. If beam_loading.expected_length is already set (> 0), returns it.
    2. Otherwise, determines yarn length on the beam from:
       a. SizingBeamAssignment.beam_yarn_length for this beam
       b. Or Beam.length
       c. Or sizing_outcome.set_length_meter (prorated by total_beams)
    3. Retrieves shortage percentage from beam_loading.shortage or sizing_outcome.total_set_shortage.
    4. Applies established factory production formula:
       expected_length = yarn_length * (1 - shortage / 100)
    5. Preserves full Decimal precision without premature rounding.
    """
    if beam_loading.expected_length is not None and beam_loading.expected_length > Decimal("0.000000"):
        return beam_loading.expected_length

    beam = beam_loading.beam
    so = beam_loading.sizing_outcome
    yarn_length = None

    # Check SizingBeamAssignment
    if so and so.yarn_outcome_id:
        from factory.yarn.sizing.models import SizingBeamAssignment
        sba = SizingBeamAssignment.objects.filter(
            yarn_outcome=so.yarn_outcome,
            beam=beam
        ).order_by("-id").first()
        if sba and sba.beam_yarn_length:
            val = sba.get_beam_yarn_length(beam.id)
            if val is not None:
                try:
                    yarn_length = Decimal(str(val))
                except Exception:
                    pass

    if yarn_length is None and beam and beam.length:
        yarn_length = Decimal(str(beam.length))

    if yarn_length is None and so and so.set_length_meter:
        total_beams = so.total_beams or 1
        yarn_length = Decimal(str(so.set_length_meter)) / Decimal(str(total_beams))

    if yarn_length is None:
        yarn_length = Decimal("0.000000")

    # Shortage percentage
    shortage_pct = Decimal("0.000000")
    if beam_loading.shortage is not None:
        shortage_pct = Decimal(str(beam_loading.shortage))
    elif so and so.total_set_shortage is not None:
        shortage_pct = Decimal(str(so.total_set_shortage))

    # Formula: expected = yarn_length * (1 - shortage / 100)
    expected = yarn_length * (Decimal("1.000000") - (shortage_pct / Decimal("100.000000")))
    if expected < Decimal("0.000000"):
        expected = Decimal("0.000000")

    return expected


def dismount_beam_loading(
    beam_loading_or_id,
    dismount_date=None,
    remarks="",
    expected_length_override=None,
    user=None,
    request=None,
):
    """
    Reconciles actual cloth length against expected length and completes beam loading:
      1. Locks BeamLoading, Beam, Loom with select_for_update().
      2. Validates that loading cycle is active and not already completed.
      3. Sums actual cloth length from ClothPatch.productive_length for this specific loading cycle.
         If no patches exist, falls back to sum of Production.meters_produced for this cycle.
      4. Calculates expected cloth length using the verified factory formula.
      5. Calculates difference = actual_length - expected_length (+ exceeds, - below, 0 equal).
      6. Calculates production_percentage = (actual_length / expected_length) * 100 (if expected > 0).
      7. Stores / updates BeamDismountReconciliation record atomically.
      8. Sets BeamLoading.status = COMPLETED, records dismount_date and dismounted_by.
      9. Sets Beam.status = AVAILABLE for safe reuse.
     10. Sets Loom.status = ACTIVE.
     11. Releases any active SizingBeamAssignment for this beam.
    """
    loading_id = beam_loading_or_id.id if hasattr(beam_loading_or_id, "id") else beam_loading_or_id

    with transaction.atomic():
        try:
            loading = (
                BeamLoading.objects
                .select_for_update()
                .select_related("beam", "loom", "sizing_outcome")
                .get(id=loading_id)
            )
        except BeamLoading.DoesNotExist:
            raise ValidationError({"detail": f"BeamLoading #{loading_id} does not exist."})

        if loading.status == BeamLoading.StatusChoices.COMPLETED:
            raise ValidationError({"detail": f"BeamLoading #{loading_id} is already marked completed / dismounted."})

        beam = Beam.objects.select_for_update().get(id=loading.beam_id)
        loom = Loom.objects.select_for_update().get(id=loading.loom_id)

        # Calculate actual length from ClothPatch
        from factory.cloth.models import ClothPatch
        patch_sum = (
            ClothPatch.objects.filter(beam_loading=loading)
            .aggregate(s=Sum("productive_length"))["s"]
        )
        if patch_sum is not None:
            actual_length = Decimal(str(patch_sum))
        else:
            # Fallback to Production.meters_produced if patches were not used
            prod_sum = (
                loading.productions.aggregate(s=Sum("meters_produced"))["s"]
            )
            actual_length = Decimal(str(prod_sum)) if prod_sum is not None else Decimal("0.000000")

        # Determine expected length
        if expected_length_override is not None:
            expected_length = Decimal(str(expected_length_override))
        else:
            expected_length = calculate_expected_cloth_length(loading)

        # Difference and percentage
        difference = actual_length - expected_length
        if expected_length > Decimal("0.000000"):
            production_percentage = (actual_length / expected_length) * Decimal("100.0000")
        else:
            production_percentage = None

        d_date = dismount_date or timezone.now().date()

        # Update or create BeamDismountReconciliation
        from factory.beam.models import BeamDismountReconciliation
        reconciliation, _ = BeamDismountReconciliation.objects.update_or_create(
            beam_loading=loading,
            defaults={
                "expected_length": expected_length,
                "actual_length": actual_length,
                "difference": difference,
                "production_percentage": production_percentage,
                "dismount_date": d_date,
                "dismounted_by": user,
                "remarks": remarks or "",
            }
        )

        # Update loading
        loading.status = BeamLoading.StatusChoices.COMPLETED
        loading.expected_length = expected_length
        loading.dismount_date = d_date
        loading.dismounted_by = user
        loading.updated_by = user
        loading.save(update_fields=[
            "status",
            "expected_length",
            "dismount_date",
            "dismounted_by",
            "updated_by",
            "updated_at",
        ])

        # Release Beam and Loom
        beam.status = Beam.StatusChoices.AVAILABLE
        beam.updated_by = user
        beam.save(update_fields=["status", "updated_by", "updated_at"])

        loom.status = Loom.StatusChoices.ACTIVE
        loom.updated_by = user
        loom.save(update_fields=["status", "updated_by", "updated_at"])

        # Release SizingBeamAssignment
        from factory.yarn.sizing.models import SizingBeamAssignment
        active_sba_list = SizingBeamAssignment.objects.filter(
            beam=beam
        ).exclude(status=SizingBeamAssignment.StatusChoices.RELEASED)
        for sba in active_sba_list:
            sba.status = SizingBeamAssignment.StatusChoices.RELEASED
            sba.released_at = timezone.now()
            sba.updated_by = user
            sba.save(update_fields=["status", "released_at", "updated_by", "updated_at"])

        log_activity(
            request=request,
            action="Dismount Beam",
            description=(
                f"Dismounted Beam '{beam.beam_number}' from Loom '{loom.loom_code}' (Loading #{loading.id}). "
                f"Actual: {actual_length}m, Expected: {expected_length}m, Difference: {difference}m."
            ),
            module="Factory – Beam Loading",
            status="Success",
            user=user,
        )

        return reconciliation
