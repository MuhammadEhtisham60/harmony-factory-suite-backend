"""
Models for Cloth Production and Inventory.

Includes:
- ClothName: Master registry of cloth names/qualities.
- ClothPatch: Individual cloth patch/bundle produced on a loom from a mounted beam.
- ClothStock: Consolidated master stock record per ClothName (clean stock only).
- CleanClothStock: Clean cloth inventory classified from patches.
- DefectedClothStock: Defective cloth inventory classified from patches.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum


class ClothName(models.Model):
    """
    Master list of cloth names / fabric quality specifications.
    Enforces normalized whitespace and case-insensitive uniqueness.
    """
    name = models.CharField(
        max_length=150,
        unique=True,
        help_text="Cloth name / quality title (e.g. Cotton 40/40, Poplin 60/60)"
    )

    warp_count = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Warp yarn count (e.g. 40/1, 20/1)"
    )

    weft_count = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Weft yarn count (e.g. 40/1, 20/1)"
    )

    reed_count = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Reed count / dents per inch"
    )

    pick_count = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Pick count / PPI"
    )

    reed_width = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Reed width in inches"
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description, construction details, or remarks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cloth_names"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_cloth_names"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Cloth Name"
        verbose_name_plural = "Cloth Names"

    def clean(self):
        super().clean()
        if self.name:
            self.name = self.name.strip()
            qs = ClothName.objects.filter(name__iexact=self.name)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"name": ["Cloth name with this name already exists (case-insensitive)."]})
        if self.warp_count:
            self.warp_count = self.warp_count.strip()
        if self.weft_count:
            self.weft_count = self.weft_count.strip()

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip()
        if self.warp_count:
            self.warp_count = self.warp_count.strip()
        if self.weft_count:
            self.weft_count = self.weft_count.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ClothPatch(models.Model):
    """
    Individual cloth patch/bundle removed from a Loom.
    Bound to the exact BeamLoading production cycle, Beam, and Loom.
    Preserved permanently as historical production record.
    """
    loom = models.ForeignKey(
        "factory.Loom",
        on_delete=models.PROTECT,
        related_name="cloth_patches",
        help_text="Loom where this patch was woven"
    )

    beam = models.ForeignKey(
        "factory.Beam",
        on_delete=models.PROTECT,
        related_name="cloth_patches",
        help_text="Warp beam installed when patch was woven"
    )

    beam_loading = models.ForeignKey(
        "factory.BeamLoading",
        on_delete=models.PROTECT,
        related_name="cloth_patches",
        help_text="Specific beam-loading production cycle"
    )

    patch_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique patch identifier (e.g. PATCH-2026-0001)"
    )

    set_no = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Sizing set number inherited from beam loading (e.g. SET-2, SET-4)"
    )

    cloth_name = models.ForeignKey(
        ClothName,
        on_delete=models.PROTECT,
        related_name="cloth_patches",
        help_text="Cloth name / quality master reference"
    )

    patch_date = models.DateField(
        help_text="Date patch was cut and removed from loom"
    )

    bundle_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of bundles/rolls in this patch"
    )

    productive_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Measured actual cloth length for that patch in meters"
    )

    remarks = models.TextField(
        blank=True,
        default="",
        help_text="Operator notes or quality observations"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cloth_patches"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_cloth_patches"
    )

    class Meta:
        ordering = ["-patch_date", "-id"]
        verbose_name = "Cloth Patch"
        verbose_name_plural = "Cloth Patches"
        indexes = [
            models.Index(fields=["patch_number"], name="factory_cp_patch_no_idx"),
            models.Index(fields=["beam_loading"], name="factory_cp_bl_idx"),
            models.Index(fields=["cloth_name"], name="factory_cp_cn_idx"),
            models.Index(fields=["patch_date"], name="factory_cp_date_idx"),
            models.Index(fields=["set_no"], name="factory_cp_set_no_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.set_no and self.beam_loading:
            if getattr(self.beam_loading, "sizing_outcome", None):
                self.set_no = self.beam_loading.sizing_outcome.set_no or ""
            elif getattr(self.beam_loading, "set_no", None):
                self.set_no = self.beam_loading.set_no or ""
        if not self.patch_number or str(self.patch_number).strip().lower() in ("", "auto"):
            self.patch_number = self.generate_next_patch_number(self.beam_loading)
        super().save(*args, **kwargs)

    @classmethod
    def generate_next_patch_number(cls, beam_loading_or_id):
        """
        Auto-generates sequential patch identifier formatted as:
        patch-set-{set_no}-{loom_number}---{beam_number}--{bundle_count:04d}
        Example:
        patch-set-2-l-101---Bm-101--0001
        """
        import re
        from factory.beam.models import BeamLoading

        if isinstance(beam_loading_or_id, BeamLoading):
            loading = beam_loading_or_id
        else:
            try:
                loading = (
                    BeamLoading.objects
                    .select_related("beam", "loom", "sizing_outcome")
                    .get(id=beam_loading_or_id)
                )
            except Exception:
                loading = None

        # 1. Set part (e.g. "set-2" from "SET-2", "2", "SET-4" -> "set-4")
        raw_set = ""
        if loading and loading.sizing_outcome and loading.sizing_outcome.set_no:
            raw_set = loading.sizing_outcome.set_no
        elif loading and getattr(loading, "set_no", None):
            raw_set = loading.set_no

        if raw_set:
            s = str(raw_set).strip()
            m = re.match(r"^set[-_\s]*(.+)$", s, re.IGNORECASE)
            val = m.group(1).strip() if m else s
            val = re.sub(r"\s+", "-", val).lower()
            set_part = f"set-{val}"
        else:
            set_part = "set-1"

        # 2. Loom part (e.g. "l-101" from "L-101", "101", "LOOM-101")
        raw_loom = ""
        if loading and loading.loom and loading.loom.loom_code:
            raw_loom = loading.loom.loom_code
        elif loading and getattr(loading, "loom_id", None):
            raw_loom = str(loading.loom_id)

        if raw_loom:
            s = str(raw_loom).strip()
            m = re.match(r"^(?:loom|l)[-_\s]*(.+)$", s, re.IGNORECASE)
            val = m.group(1).strip() if m else s
            val = re.sub(r"\s+", "-", val).lower()
            loom_part = f"l-{val}"
        else:
            loom_part = "l-0"

        # 3. Beam part (e.g. "Bm-101" from "BM-101", "BM-0101", "101")
        raw_beam = ""
        if loading and loading.beam and loading.beam.beam_number:
            raw_beam = loading.beam.beam_number
        elif loading and getattr(loading, "beam_id", None):
            raw_beam = str(loading.beam_id)

        if raw_beam:
            s = str(raw_beam).strip()
            m = re.match(r"^(?:beam|bm)[-_\s]*(.+)$", s, re.IGNORECASE)
            val = m.group(1).strip() if m else s
            val = re.sub(r"\s+", "-", val)
            beam_part = f"Bm-{val}"
        else:
            beam_part = "Bm-0"

        # 4. Sequential roll/bundle count (e.g. 0001, 0002)
        prefix = f"patch-{set_part}-{loom_part}---{beam_part}--"

        existing_matches = cls.objects.filter(patch_number__istartswith=prefix).values_list("patch_number", flat=True)
        max_seq = 0
        pattern = re.compile(re.escape(prefix) + r"(\d+)$", re.IGNORECASE)
        for p_num in existing_matches:
            match = pattern.match(p_num)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_seq:
                        max_seq = num
                except ValueError:
                    pass

        if max_seq > 0:
            next_seq = max_seq + 1
        else:
            if loading and getattr(loading, "pk", None):
                loading_count = cls.objects.filter(beam_loading=loading).count()
                next_seq = loading_count + 1
            else:
                next_seq = 1

        candidate = f"{prefix}{next_seq:04d}"
        while cls.objects.filter(patch_number__iexact=candidate).exists():
            next_seq += 1
            candidate = f"{prefix}{next_seq:04d}"

        return candidate

    def __str__(self):
        cloth_title = self.cloth_name.name if self.cloth_name else "Unknown"
        return f"Patch #{self.patch_number} ({cloth_title}) - {self.productive_length}m"

    @property
    def clean_allocated_length(self):
        total = self.clean_stocks.aggregate(s=Sum("total_length"))["s"]
        return total if total is not None else Decimal("0.000000")

    @property
    def defected_allocated_length(self):
        total = self.defected_stocks.aggregate(s=Sum("total_length"))["s"]
        return total if total is not None else Decimal("0.000000")

    @property
    def classified_length(self):
        return self.clean_allocated_length + self.defected_allocated_length

    @property
    def unallocated_length(self):
        rem = self.productive_length - self.classified_length
        return rem if rem > Decimal("0") else Decimal("0.000000")


class ClothStock(models.Model):
    """
    Consolidated master stock record per ClothName.
    total_length represents CLEAN STOCK ONLY.
    Defective stock is calculated separately.
    """
    cloth_name = models.OneToOneField(
        ClothName,
        on_delete=models.PROTECT,
        related_name="stock",
        help_text="Target cloth name master reference"
    )

    total_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total clean stock length in meters (Clean stock only; never includes defected stock)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cloth_stocks"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_cloth_stocks"
    )

    class Meta:
        ordering = ["cloth_name__name"]
        verbose_name = "Cloth Stock"
        verbose_name_plural = "Cloth Stocks"

    def __str__(self):
        cloth_title = self.cloth_name.name if self.cloth_name else "Unknown"
        return f"{cloth_title} Stock ({self.total_length}m clean)"


class CleanClothStock(models.Model):
    """
    Individual clean-stock records linked to originating patches.
    total_length must be strictly positive.
    The sum of clean + defected lengths for a patch cannot exceed productive_length.
    """
    cloth_stock = models.ForeignKey(
        ClothStock,
        on_delete=models.PROTECT,
        related_name="clean_records",
        help_text="Consolidated master cloth stock"
    )

    cloth_patch = models.ForeignKey(
        ClothPatch,
        on_delete=models.PROTECT,
        related_name="clean_stocks",
        help_text="Originating cloth patch"
    )

    total_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Clean cloth length in meters (> 0)"
    )

    stock_date = models.DateField(
        help_text="Stock classification date"
    )

    remarks = models.TextField(
        blank=True,
        default="",
        help_text="Inspection or allocation remarks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_clean_cloth_stocks"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_clean_cloth_stocks"
    )

    class Meta:
        ordering = ["-stock_date", "-id"]
        verbose_name = "Clean Cloth Stock"
        verbose_name_plural = "Clean Cloth Stocks"
        indexes = [
            models.Index(fields=["cloth_stock", "stock_date"], name="factory_ccs_stock_dt_idx"),
            models.Index(fields=["cloth_patch"], name="factory_ccs_patch_idx"),
        ]

    def __str__(self):
        patch_no = self.cloth_patch.patch_number if self.cloth_patch else "N/A"
        return f"Clean Stock #{self.id} for Patch {patch_no} ({self.total_length}m)"


class DefectedClothStock(models.Model):
    """
    Individual defective-stock records linked to originating patches.
    total_length must be strictly positive.
    The sum of clean + defected lengths for a patch cannot exceed productive_length.
    """
    cloth_stock = models.ForeignKey(
        ClothStock,
        on_delete=models.PROTECT,
        related_name="defected_records",
        help_text="Consolidated master cloth stock"
    )

    cloth_patch = models.ForeignKey(
        ClothPatch,
        on_delete=models.PROTECT,
        related_name="defected_stocks",
        help_text="Originating cloth patch"
    )

    defect_type = models.CharField(
        max_length=150,
        help_text="Type of defect (e.g. Oil Stain, Warp Break, Slub, Hole, Mispick, Broken Ends)"
    )

    defect_description = models.TextField(
        blank=True,
        default="",
        help_text="Detailed description of defect"
    )

    total_length = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Defective cloth length in meters (> 0)"
    )

    stock_date = models.DateField(
        help_text="Defect classification date"
    )

    remarks = models.TextField(
        blank=True,
        default="",
        help_text="Inspection or allocation remarks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_defected_cloth_stocks"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_defected_cloth_stocks"
    )

    class Meta:
        ordering = ["-stock_date", "-id"]
        verbose_name = "Defected Cloth Stock"
        verbose_name_plural = "Defected Cloth Stocks"
        indexes = [
            models.Index(fields=["cloth_stock", "stock_date"], name="factory_dcs_stock_dt_idx"),
            models.Index(fields=["cloth_patch"], name="factory_dcs_patch_idx"),
            models.Index(fields=["defect_type"], name="factory_dcs_type_idx"),
        ]

    def __str__(self):
        patch_no = self.cloth_patch.patch_number if self.cloth_patch else "N/A"
        return f"Defect #{self.id} ({self.defect_type}) for Patch {patch_no} ({self.total_length}m)"
