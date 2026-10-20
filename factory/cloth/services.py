"""
Service layer for Cloth Production and Inventory.

Encapsulates:
- Atomic patch creation and beam-loading lifecycle advances.
- Atomic stock allocation invariant enforcement:
    clean_length + defected_length <= patch.productive_length
- Database locking with select_for_update() to prevent race conditions.
- Automatic transactional synchronization of ClothStock.total_length (clean stock only).
"""

import logging
from decimal import Decimal
from django.db import transaction, IntegrityError
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from factory.beam.models import Beam, BeamLoading
from factory.loom.models import Loom
from audit_logs.utils import log_activity
from .models import (
    ClothName,
    ClothPatch,
    ClothStock,
    CleanClothStock,
    DefectedClothStock,
)

logger = logging.getLogger(__name__)


def create_cloth_patch(
    beam_loading_or_id,
    patch_number,
    cloth_name_or_id,
    patch_date,
    productive_length,
    bundle_count=1,
    loom_or_id=None,
    beam_or_id=None,
    remarks="",
    user=None,
    request=None,
):
    """
    Atomically records a cloth patch cut from a loom:
      1. Locks BeamLoading with select_for_update().
      2. Validates BeamLoading is active (Loaded or In Production).
      3. Validates/derives Beam and Loom matches.
      4. Advances BeamLoading and Beam to In Production if currently Loaded.
      5. Validates productive_length > 0.
      6. Creates ClothPatch record.
      7. Automatically ensures a ClothStock master exists for cloth_name.
    """
    loading_id = beam_loading_or_id.id if hasattr(beam_loading_or_id, "id") else beam_loading_or_id

    try:
        length_dec = Decimal(str(productive_length))
    except Exception:
        raise ValidationError({"productive_length": ["Invalid productive_length value."]})

    if length_dec <= Decimal("0.000000"):
        raise ValidationError({"productive_length": ["Productive length must be strictly positive (> 0)."]})

    with transaction.atomic():
        try:
            loading = (
                BeamLoading.objects
                .select_for_update()
                .select_related("beam", "loom")
                .get(id=loading_id)
            )
        except BeamLoading.DoesNotExist:
            raise ValidationError({"beam_loading": [f"BeamLoading #{loading_id} does not exist."]})

        if loading.status in [BeamLoading.StatusChoices.COMPLETED, BeamLoading.StatusChoices.EMPTY]:
            raise ValidationError({
                "beam_loading": [
                    f"BeamLoading #{loading.id} is already '{loading.status}'. "
                    f"Patches can only be recorded against active loading cycles."
                ]
            })

        # Resolve and validate Beam
        beam_id = beam_or_id.id if hasattr(beam_or_id, "id") else (beam_or_id or loading.beam_id)
        if beam_id != loading.beam_id:
            raise ValidationError({
                "beam": [
                    f"Selected Beam #{beam_id} does not match Beam #{loading.beam_id} "
                    f"mounted on BeamLoading #{loading.id}."
                ]
            })
        beam = Beam.objects.select_for_update().get(id=loading.beam_id)

        # Resolve and validate Loom
        loom_id = loom_or_id.id if hasattr(loom_or_id, "id") else (loom_or_id or loading.loom_id)
        if loom_id != loading.loom_id:
            raise ValidationError({
                "loom": [
                    f"Selected Loom #{loom_id} does not match Loom #{loading.loom_id} "
                    f"associated with BeamLoading #{loading.id}."
                ]
            })
        loom = Loom.objects.select_for_update().get(id=loading.loom_id)

        # Resolve ClothName
        if isinstance(cloth_name_or_id, ClothName):
            cloth_name_obj = cloth_name_or_id
        elif cloth_name_or_id:
            try:
                cloth_name_obj = ClothName.objects.get(id=cloth_name_or_id)
            except (ClothName.DoesNotExist, ValueError):
                # Check by name string or create on the fly
                cloth_name_obj = ClothName.objects.filter(name__iexact=str(cloth_name_or_id).strip()).first()
                if not cloth_name_obj:
                    cloth_name_obj = ClothName.objects.create(name=str(cloth_name_or_id).strip(), created_by=user)
        elif getattr(loading, "cloth_name", None):
            cloth_name_obj = loading.cloth_name
        elif getattr(loading, "cloth_quality", None) and str(loading.cloth_quality).strip():
            cloth_name_obj, _ = ClothName.objects.get_or_create(name=loading.cloth_quality.strip(), defaults={"created_by": user})
        else:
            raise ValidationError({"cloth_name": ["Cloth quality / name could not be resolved from active loading."]})

        # Advance BeamLoading and Beam to IN_PRODUCTION if currently LOADED
        if loading.status == BeamLoading.StatusChoices.LOADED:
            loading.status = BeamLoading.StatusChoices.IN_PRODUCTION
            loading.updated_by = user
            loading.save(update_fields=["status", "updated_by", "updated_at"])

        if beam.status != Beam.StatusChoices.IN_PRODUCTION:
            beam.status = Beam.StatusChoices.IN_PRODUCTION
            beam.updated_by = user
            beam.save(update_fields=["status", "updated_by", "updated_at"])

        if loom.status != Loom.StatusChoices.PRODUCTION:
            loom.status = Loom.StatusChoices.PRODUCTION
            loom.updated_by = user
            loom.save(update_fields=["status", "updated_by", "updated_at"])

        # Resolve target patch_number: if duplicate sequential roll code is submitted,
        # auto-increment sequence so multiple pieces cut from the same loom/beam cycle succeed seamlessly.
        import re
        target_patch_number = str(patch_number).strip() if patch_number else ""
        if target_patch_number and ClothPatch.objects.filter(patch_number=target_patch_number).exists():
            m = re.match(r"^(.*--)(\d+)$", target_patch_number)
            if m:
                prefix, num_str = m.group(1), m.group(2)
                seq = int(num_str) + 1
                while ClothPatch.objects.filter(patch_number=f"{prefix}{str(seq).zfill(len(num_str))}").exists():
                    seq += 1
                target_patch_number = f"{prefix}{str(seq).zfill(len(num_str))}"

        # Create ClothPatch
        try:
            patch = ClothPatch.objects.create(
                loom=loom,
                beam=beam,
                beam_loading=loading,
                patch_number=target_patch_number,
                cloth_name=cloth_name_obj,
                patch_date=patch_date,
                bundle_count=int(bundle_count or 1),
                productive_length=length_dec,
                remarks=remarks or "",
                created_by=user,
                updated_by=user,
            )
        except IntegrityError as exc:
            logger.error(f"IntegrityError creating ClothPatch: {exc}")
            raise ValidationError({"patch_number": [f"Patch number '{target_patch_number}' already exists."]})

        # Ensure ClothStock master row exists
        ClothStock.objects.get_or_create(
            cloth_name=cloth_name_obj,
            defaults={
                "total_length": Decimal("0.000000"),
                "created_by": user,
                "updated_by": user,
            }
        )

        log_activity(
            request=request,
            action="Create Cloth Patch",
            description=(
                f"Recorded ClothPatch '{patch.patch_number}' ({cloth_name_obj.name}, {patch.productive_length}m) "
                f"on Loom '{loom.loom_code}' from Beam '{beam.beam_number}' (Loading #{loading.id})."
            ),
            module="Factory – Cloth Production",
            status="Success",
            user=user,
        )

        return patch


def validate_patch_allocation(
    cloth_patch,
    new_length,
    cloth_stock=None,
    exclude_clean_id=None,
    exclude_defected_id=None,
):
    """
    Validates that:
      1. new_length is strictly positive (> 0).
      2. If cloth_stock is provided, its cloth_name matches cloth_patch.cloth_name.
      3. Total classified length (existing clean + existing defected + new_length)
         does not exceed cloth_patch.productive_length.
    """
    try:
        alloc_dec = Decimal(str(new_length))
    except Exception:
        raise ValidationError({"total_length": ["Invalid length value."]})

    if alloc_dec <= Decimal("0.000000"):
        raise ValidationError({"total_length": ["Allocated length must be strictly positive (> 0)."]})

    # Validate cloth_name consistency
    if cloth_stock:
        if cloth_stock.cloth_name_id != cloth_patch.cloth_name_id:
            raise ValidationError({
                "cloth_stock": [
                    f"Cloth stock cloth name '{cloth_stock.cloth_name.name}' does not match "
                    f"patch cloth name '{cloth_patch.cloth_name.name}'."
                ]
            })

    # Compute clean allocations for this patch
    clean_qs = CleanClothStock.objects.filter(cloth_patch=cloth_patch)
    if exclude_clean_id:
        clean_qs = clean_qs.exclude(id=exclude_clean_id)
    current_clean = clean_qs.aggregate(s=Sum("total_length"))["s"] or Decimal("0.000000")

    # Compute defected allocations for this patch
    defected_qs = DefectedClothStock.objects.filter(cloth_patch=cloth_patch)
    if exclude_defected_id:
        defected_qs = defected_qs.exclude(id=exclude_defected_id)
    current_defected = defected_qs.aggregate(s=Sum("total_length"))["s"] or Decimal("0.000000")

    already_classified = current_clean + current_defected
    proposed_total = already_classified + alloc_dec

    if proposed_total > cloth_patch.productive_length:
        remaining = cloth_patch.productive_length - already_classified
        if remaining < Decimal("0"):
            remaining = Decimal("0.000000")
        raise ValidationError({
            "total_length": [
                f"Proposed allocation of {alloc_dec}m exceeds available patch productive length. "
                f"Patch productive length: {cloth_patch.productive_length}m. "
                f"Already classified: {already_classified}m (Clean: {current_clean}m, Defected: {current_defected}m). "
                f"Remaining unallocated: {remaining}m."
            ]
        })

    return alloc_dec


def sync_cloth_stock_clean_total(cloth_stock_or_id):
    """
    Transactionally recalculates ClothStock.total_length as the exact sum of
    all linked CleanClothStock records.
    Never includes defected stock in total_length.
    """
    stock_id = cloth_stock_or_id.id if hasattr(cloth_stock_or_id, "id") else cloth_stock_or_id
    with transaction.atomic():
        stock = ClothStock.objects.select_for_update().get(id=stock_id)
        clean_sum = (
            CleanClothStock.objects.filter(cloth_stock=stock)
            .aggregate(s=Sum("total_length"))["s"]
            or Decimal("0.000000")
        )
        stock.total_length = clean_sum
        stock.save(update_fields=["total_length", "updated_at"])
        return stock


def create_clean_cloth_stock(
    cloth_stock_or_id,
    cloth_patch_or_id,
    total_length,
    stock_date,
    remarks="",
    user=None,
    request=None,
):
    """
    Atomically allocates clean cloth stock from a patch.
    """
    stock_id = cloth_stock_or_id.id if hasattr(cloth_stock_or_id, "id") else cloth_stock_or_id
    patch_id = cloth_patch_or_id.id if hasattr(cloth_patch_or_id, "id") else cloth_patch_or_id

    with transaction.atomic():
        try:
            cloth_stock = ClothStock.objects.select_for_update().select_related("cloth_name").get(id=stock_id)
        except ClothStock.DoesNotExist:
            raise ValidationError({"cloth_stock": [f"ClothStock #{stock_id} does not exist."]})

        try:
            cloth_patch = ClothPatch.objects.select_for_update().select_related("cloth_name").get(id=patch_id)
        except ClothPatch.DoesNotExist:
            raise ValidationError({"cloth_patch": [f"ClothPatch #{patch_id} does not exist."]})

        alloc_dec = validate_patch_allocation(
            cloth_patch=cloth_patch,
            new_length=total_length,
            cloth_stock=cloth_stock,
        )

        clean_record = CleanClothStock.objects.create(
            cloth_stock=cloth_stock,
            cloth_patch=cloth_patch,
            total_length=alloc_dec,
            stock_date=stock_date,
            remarks=remarks or "",
            created_by=user,
            updated_by=user,
        )

        sync_cloth_stock_clean_total(cloth_stock)

        log_activity(
            request=request,
            action="Add Clean Cloth Stock",
            description=(
                f"Allocated {clean_record.total_length}m clean cloth to stock for '{cloth_stock.cloth_name.name}' "
                f"from Patch #{cloth_patch.patch_number}."
            ),
            module="Factory – Cloth Stock",
            status="Success",
            user=user,
        )

        return clean_record


def update_clean_cloth_stock(
    clean_stock_or_id,
    total_length=None,
    stock_date=None,
    remarks=None,
    user=None,
    request=None,
):
    """
    Atomically updates a clean cloth stock record.
    """
    rec_id = clean_stock_or_id.id if hasattr(clean_stock_or_id, "id") else clean_stock_or_id

    with transaction.atomic():
        try:
            clean_rec = (
                CleanClothStock.objects
                .select_for_update()
                .select_related("cloth_stock", "cloth_patch")
                .get(id=rec_id)
            )
        except CleanClothStock.DoesNotExist:
            raise ValidationError({"detail": f"CleanClothStock #{rec_id} does not exist."})

        # Lock the patch
        patch = ClothPatch.objects.select_for_update().get(id=clean_rec.cloth_patch_id)

        update_fields = ["updated_at"]
        if total_length is not None:
            alloc_dec = validate_patch_allocation(
                cloth_patch=patch,
                new_length=total_length,
                cloth_stock=clean_rec.cloth_stock,
                exclude_clean_id=clean_rec.id,
            )
            clean_rec.total_length = alloc_dec
            update_fields.append("total_length")

        if stock_date is not None:
            clean_rec.stock_date = stock_date
            update_fields.append("stock_date")

        if remarks is not None:
            clean_rec.remarks = remarks
            update_fields.append("remarks")

        if user:
            clean_rec.updated_by = user
            update_fields.append("updated_by")

        clean_rec.save(update_fields=update_fields)
        sync_cloth_stock_clean_total(clean_rec.cloth_stock)

        log_activity(
            request=request,
            action="Update Clean Cloth Stock",
            description=f"Updated CleanClothStock #{clean_rec.id} ({clean_rec.total_length}m).",
            module="Factory – Cloth Stock",
            status="Success",
            user=user,
        )

        return clean_rec


def delete_clean_cloth_stock(clean_stock_or_id, user=None, request=None):
    """
    Atomically deletes a clean cloth stock record and resynchronizes total_length.
    """
    rec_id = clean_stock_or_id.id if hasattr(clean_stock_or_id, "id") else clean_stock_or_id

    with transaction.atomic():
        try:
            clean_rec = (
                CleanClothStock.objects
                .select_for_update()
                .select_related("cloth_stock")
                .get(id=rec_id)
            )
        except CleanClothStock.DoesNotExist:
            raise ValidationError({"detail": f"CleanClothStock #{rec_id} does not exist."})

        stock = clean_rec.cloth_stock
        clean_rec.delete()
        sync_cloth_stock_clean_total(stock)

        log_activity(
            request=request,
            action="Delete Clean Cloth Stock",
            description=f"Deleted CleanClothStock #{rec_id}.",
            module="Factory – Cloth Stock",
            status="Success",
            user=user,
        )


def create_defected_cloth_stock(
    cloth_stock_or_id,
    cloth_patch_or_id,
    defect_type,
    total_length,
    stock_date,
    defect_description="",
    remarks="",
    user=None,
    request=None,
):
    """
    Atomically records a defected cloth stock record linked to a patch.
    """
    stock_id = cloth_stock_or_id.id if hasattr(cloth_stock_or_id, "id") else cloth_stock_or_id
    patch_id = cloth_patch_or_id.id if hasattr(cloth_patch_or_id, "id") else cloth_patch_or_id

    if not str(defect_type or "").strip():
        raise ValidationError({"defect_type": ["Defect type cannot be blank."]})

    with transaction.atomic():
        try:
            cloth_stock = ClothStock.objects.select_for_update().select_related("cloth_name").get(id=stock_id)
        except ClothStock.DoesNotExist:
            raise ValidationError({"cloth_stock": [f"ClothStock #{stock_id} does not exist."]})

        try:
            cloth_patch = ClothPatch.objects.select_for_update().select_related("cloth_name").get(id=patch_id)
        except ClothPatch.DoesNotExist:
            raise ValidationError({"cloth_patch": [f"ClothPatch #{patch_id} does not exist."]})

        alloc_dec = validate_patch_allocation(
            cloth_patch=cloth_patch,
            new_length=total_length,
            cloth_stock=cloth_stock,
        )

        defected_record = DefectedClothStock.objects.create(
            cloth_stock=cloth_stock,
            cloth_patch=cloth_patch,
            defect_type=str(defect_type).strip(),
            defect_description=defect_description or "",
            total_length=alloc_dec,
            stock_date=stock_date,
            remarks=remarks or "",
            created_by=user,
            updated_by=user,
        )

        log_activity(
            request=request,
            action="Add Defected Cloth Stock",
            description=(
                f"Recorded defect '{defected_record.defect_type}' ({defected_record.total_length}m) "
                f"for '{cloth_stock.cloth_name.name}' from Patch #{cloth_patch.patch_number}."
            ),
            module="Factory – Defected Stock",
            status="Success",
            user=user,
        )

        return defected_record


def update_defected_cloth_stock(
    defected_stock_or_id,
    defect_type=None,
    total_length=None,
    stock_date=None,
    defect_description=None,
    remarks=None,
    user=None,
    request=None,
):
    """
    Atomically updates a defected cloth stock record.
    """
    rec_id = defected_stock_or_id.id if hasattr(defected_stock_or_id, "id") else defected_stock_or_id

    with transaction.atomic():
        try:
            defected_rec = (
                DefectedClothStock.objects
                .select_for_update()
                .select_related("cloth_stock", "cloth_patch")
                .get(id=rec_id)
            )
        except DefectedClothStock.DoesNotExist:
            raise ValidationError({"detail": f"DefectedClothStock #{rec_id} does not exist."})

        patch = ClothPatch.objects.select_for_update().get(id=defected_rec.cloth_patch_id)

        update_fields = ["updated_at"]
        if defect_type is not None:
            if not str(defect_type).strip():
                raise ValidationError({"defect_type": ["Defect type cannot be blank."]})
            defected_rec.defect_type = str(defect_type).strip()
            update_fields.append("defect_type")

        if defect_description is not None:
            defected_rec.defect_description = defect_description
            update_fields.append("defect_description")

        if total_length is not None:
            alloc_dec = validate_patch_allocation(
                cloth_patch=patch,
                new_length=total_length,
                cloth_stock=defected_rec.cloth_stock,
                exclude_defected_id=defected_rec.id,
            )
            defected_rec.total_length = alloc_dec
            update_fields.append("total_length")

        if stock_date is not None:
            defected_rec.stock_date = stock_date
            update_fields.append("stock_date")

        if remarks is not None:
            defected_rec.remarks = remarks
            update_fields.append("remarks")

        if user:
            defected_rec.updated_by = user
            update_fields.append("updated_by")

        defected_rec.save(update_fields=update_fields)

        log_activity(
            request=request,
            action="Update Defected Cloth Stock",
            description=f"Updated DefectedClothStock #{defected_rec.id} ({defected_rec.total_length}m).",
            module="Factory – Defected Stock",
            status="Success",
            user=user,
        )

        return defected_rec


def delete_defected_cloth_stock(defected_stock_or_id, user=None, request=None):
    """
    Atomically deletes a defected cloth stock record.
    """
    rec_id = defected_stock_or_id.id if hasattr(defected_stock_or_id, "id") else defected_stock_or_id

    with transaction.atomic():
        try:
            defected_rec = DefectedClothStock.objects.select_for_update().get(id=rec_id)
        except DefectedClothStock.DoesNotExist:
            raise ValidationError({"detail": f"DefectedClothStock #{rec_id} does not exist."})

        defected_rec.delete()

        log_activity(
            request=request,
            action="Delete Defected Cloth Stock",
            description=f"Deleted DefectedClothStock #{rec_id}.",
            module="Factory – Defected Stock",
            status="Success",
            user=user,
        )
