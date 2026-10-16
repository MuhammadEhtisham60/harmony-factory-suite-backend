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
        ]

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
