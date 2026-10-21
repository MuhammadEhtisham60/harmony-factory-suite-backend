"""
Views for Cloth Production and Inventory.

Endpoints:
- ClothNameViewSet:        /api/v1/cloth-names/
- ClothPatchViewSet:       /api/v1/cloth-patches/
- RawStockViewSet:         /api/v1/raw-stock/
- ClothStockViewSet:       /api/v1/cloth-stock/
- CleanClothStockViewSet:  /api/v1/clean-cloth-stock/
- DefectedClothStockViewSet:/api/v1/defected-cloth-stock/
"""

from decimal import Decimal
from django.db.models import Subquery, OuterRef, Sum, Count, IntegerField, DecimalField
from django.db.models.functions import Coalesce
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import (
    ClothName,
    ClothPatch,
    ClothStock,
    CleanClothStock,
    DefectedClothStock,
)
from .serializers import (
    ClothNameSerializer,
    ClothPatchSerializer,
    ClothStockSerializer,
    CleanClothStockSerializer,
    DefectedClothStockSerializer,
)
from .filters import (
    ClothPatchFilter,
    ClothStockFilter,
    CleanClothStockFilter,
    DefectedClothStockFilter,
)
from .services import (
    sync_cloth_stock_clean_total,
    delete_clean_cloth_stock,
    delete_defected_cloth_stock,
)


class ClothNameViewSet(ModelViewSet):
    """
    CRUD API for ClothName master items.
    """
    queryset = ClothName.objects.all().order_by("name")
    serializer_class = ClothNameSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description", "warp_count", "weft_count"]
    ordering_fields = [
        "name", "warp_count", "weft_count", "reed_count", "pick_count", "reed_width",
        "created_at", "updated_at", "id"
    ]
    ordering = ["name"]

    permission_map = {
        "GET": "cloth.view",
        "POST": "cloth.add",
        "PUT": "cloth.edit",
        "PATCH": "cloth.edit",
        "DELETE": "cloth.delete",
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        # Automatically ensure ClothStock master row exists
        ClothStock.objects.get_or_create(
            cloth_name=instance,
            defaults={
                "total_length": Decimal("0.000000"),
                "created_by": request.user,
                "updated_by": request.user,
            }
        )

        log_activity(
            request=request,
            action="Create Cloth Name",
            description=f"Created ClothName '{instance.name}' (ID: {instance.id}).",
            module="Factory – Cloth Master",
            status="Success",
            user=request.user,
        )

        out = ClothNameSerializer(instance, context={"request": request})
        return Response({
            "success": True,
            "message": f"Cloth name '{instance.name}' created successfully.",
            "data": out.data,
        }, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Cloth Name",
            description=f"Updated ClothName '{updated.name}' (ID: {updated.id}).",
            module="Factory – Cloth Master",
            status="Success",
            user=request.user,
        )

        out = ClothNameSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": f"Cloth name '{updated.name}' updated successfully.",
            "data": out.data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Protect from deletion if referenced
        if instance.cloth_patches.exists():
            raise ValidationError({
                "detail": f"Cannot delete cloth name '{instance.name}' because it is referenced by {instance.cloth_patches.count()} cloth patches."
            })
        if hasattr(instance, "stock") and (instance.stock.clean_records.exists() or instance.stock.defected_records.exists()):
            raise ValidationError({
                "detail": f"Cannot delete cloth name '{instance.name}' because it has active stock records."
            })

        # If empty stock exists, delete it first
        if hasattr(instance, "stock"):
            instance.stock.delete()

        name = instance.name
        instance.delete()

        log_activity(
            request=request,
            action="Delete Cloth Name",
            description=f"Deleted ClothName '{name}'.",
            module="Factory – Cloth Master",
            status="Success",
            user=request.user,
        )

        return Response({
            "success": True,
            "message": f"Cloth name '{name}' deleted successfully.",
        }, status=status.HTTP_200_OK)


class ClothPatchViewSet(ModelViewSet):
    """
    CRUD API for individual ClothPatches cut from looms.
    Also serves as the backing ViewSet for the Raw Stock screen.
    """
    queryset = (
        ClothPatch.objects
        .select_related("loom", "beam", "beam_loading", "cloth_name", "created_by", "updated_by")
        .prefetch_related("clean_stocks", "defected_stocks")
        .all()
    )
    serializer_class = ClothPatchSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ClothPatchFilter
    search_fields = [
        "patch_number",
        "cloth_name__name",
        "loom__loom_code",
        "beam__beam_number",
        "remarks",
    ]
    ordering_fields = [
        "patch_date",
        "patch_number",
        "productive_length",
        "bundle_count",
        "cloth_name__name",
        "loom__loom_code",
        "beam__beam_number",
        "created_at",
        "id",
    ]
    ordering = ["-patch_date", "-id"]

    permission_map = {
        "GET": "cloth.view",
        "POST": "cloth.add",
        "PUT": "cloth.edit",
        "PATCH": "cloth.edit",
        "DELETE": "cloth.delete",
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        out = ClothPatchSerializer(instance, context={"request": request})
        return Response({
            "success": True,
            "message": f"Cloth patch '{instance.patch_number}' recorded successfully.",
            "data": out.data,
        }, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    @action(detail=False, methods=["get"], url_path="next-patch-number")
    def next_patch_number(self, request):
        """
        Calculates and returns the authoritative next sequential patch identifier for a given beam loading.
        Query params:
            beam_loading: ID of the BeamLoading
        Format:
            patch-set-{set_no}-{loom_code}---{beam_code}--{roll:04d}
        """
        raw_loading_id = (
            request.query_params.get("beam_loading")
            or request.query_params.get("beamLoading")
            or request.query_params.get("beam_loading_id")
        )
        if not raw_loading_id:
            return Response(
                {"success": False, "message": "beam_loading parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from factory.beam.models import BeamLoading
        import re

        try:
            loading = (
                BeamLoading.objects
                .select_related("loom", "beam", "sizing_outcome")
                .get(id=raw_loading_id)
            )
        except (BeamLoading.DoesNotExist, ValueError):
            return Response(
                {"success": False, "message": f"BeamLoading #{raw_loading_id} does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing_count = ClothPatch.objects.filter(beam_loading=loading).count()
        next_seq = existing_count + 1

        # 1. Set Part
        raw_set = (
            getattr(loading.sizing_outcome, "set_no", "")
            if loading.sizing_outcome
            else ""
        )
        set_part = "set-1"
        if raw_set:
            s = str(raw_set).strip()
            m = re.match(r"^set[-_\s]*(.+)$", s, re.IGNORECASE)
            val = (m.group(1).strip() if m else s).replace(" ", "-").lower()
            set_part = f"set-{val}"

        # 2. Loom Part
        raw_loom = (
            loading.loom.loom_code
            if loading.loom and loading.loom.loom_code
            else (f"L-{loading.loom_id}" if loading.loom_id else "l-0")
        )
        loom_part = "l-0"
        if raw_loom:
            s = str(raw_loom).strip()
            m = re.match(r"^(?:loom|l)[-_\s]*(.+)$", s, re.IGNORECASE)
            val = (m.group(1).strip() if m else s).replace(" ", "-").lower()
            loom_part = f"l-{val}"

        # 3. Beam Part
        raw_beam = (
            loading.beam.beam_number
            if loading.beam and loading.beam.beam_number
            else (f"BM-{loading.beam_id}" if loading.beam_id else "Bm-0")
        )
        beam_part = "Bm-0"
        if raw_beam:
            s = str(raw_beam).strip()
            m = re.match(r"^(?:beam|bm)[-_\s]*(.+)$", s, re.IGNORECASE)
            val = (m.group(1).strip() if m else s).replace(" ", "-")
            beam_part = f"Bm-{val}"

        seq_str = str(next_seq).zfill(4)
        patch_number = f"patch-{set_part}-{loom_part}---{beam_part}--{seq_str}"

        while ClothPatch.objects.filter(patch_number=patch_number).exists():
            next_seq += 1
            seq_str = str(next_seq).zfill(4)
            patch_number = f"patch-{set_part}-{loom_part}---{beam_part}--{seq_str}"

        return Response({
            "success": True,
            "data": {
                "patchNumber": patch_number,
                "patch_number": patch_number,
                "sequence": next_seq,
                "beamLoadingId": loading.id,
            },
            "patchNumber": patch_number,
            "patch_number": patch_number,
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        # If productive_length changed and loading has reconciliation, re-sync reconciliation actual length
        if hasattr(updated.beam_loading, "reconciliation") and updated.beam_loading.reconciliation:
            recon = updated.beam_loading.reconciliation
            patch_sum = (
                ClothPatch.objects.filter(beam_loading=updated.beam_loading)
                .aggregate(s=Sum("productive_length"))["s"]
                or Decimal("0.000000")
            )
            recon.actual_length = Decimal(str(patch_sum))
            recon.difference = recon.actual_length - recon.expected_length
            if recon.expected_length > Decimal("0.000000"):
                recon.production_percentage = (recon.actual_length / recon.expected_length) * Decimal("100.0000")
            recon.save(update_fields=["actual_length", "difference", "production_percentage", "updated_at"])

        log_activity(
            request=request,
            action="Update Cloth Patch",
            description=f"Updated ClothPatch '{updated.patch_number}'.",
            module="Factory – Cloth Production",
            status="Success",
            user=request.user,
        )

        out = ClothPatchSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": f"Cloth patch '{updated.patch_number}' updated successfully.",
            "data": out.data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.clean_stocks.exists() or instance.defected_stocks.exists():
            raise ValidationError({
                "detail": (
                    f"Cannot delete ClothPatch '{instance.patch_number}' because it already has "
                    f"clean ({instance.clean_stocks.count()}) or defected ({instance.defected_stocks.count()}) "
                    f"stock allocations recorded against it."
                )
            })

        patch_num = instance.patch_number
        loading = instance.beam_loading
        instance.delete()

        # If loading has reconciliation, re-sync reconciliation actual length
        if hasattr(loading, "reconciliation") and loading.reconciliation:
            recon = loading.reconciliation
            patch_sum = (
                ClothPatch.objects.filter(beam_loading=loading)
                .aggregate(s=Sum("productive_length"))["s"]
                or Decimal("0.000000")
            )
            recon.actual_length = Decimal(str(patch_sum))
            recon.difference = recon.actual_length - recon.expected_length
            if recon.expected_length > Decimal("0.000000"):
                recon.production_percentage = (recon.actual_length / recon.expected_length) * Decimal("100.0000")
            recon.save(update_fields=["actual_length", "difference", "production_percentage", "updated_at"])

        log_activity(
            request=request,
            action="Delete Cloth Patch",
            description=f"Deleted ClothPatch '{patch_num}'.",
            module="Factory – Cloth Production",
            status="Success",
            user=request.user,
        )

        return Response({
            "success": True,
            "message": f"Cloth patch '{patch_num}' deleted successfully.",
        }, status=status.HTTP_200_OK)


class RawStockViewSet(ClothPatchViewSet):
    """
    Dedicated viewset for the Raw Stock screen displaying every cloth patch individually.
    Fully inherits ClothPatchViewSet functionality with pagination, filtering, and search.
    """
    pass


class ClothStockViewSet(ModelViewSet):
    """
    Consolidated Cloth Stock screen API.
    One row per ClothName.
    total_length represents clean stock only.
    defected_total_length represents defective stock.
    Optimized single-query aggregation via Subqueries avoiding N+1 and Cartesian products.
    """
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ClothStockFilter
    search_fields = ["cloth_name__name"]
    ordering_fields = ["cloth_name__name", "total_length", "created_at", "updated_at", "id"]
    ordering = ["cloth_name__name"]

    permission_map = {
        "GET": "stock.view",
        "POST": "stock.manage",
        "PUT": "stock.manage",
        "PATCH": "stock.manage",
        "DELETE": "stock.manage",
    }

    def get_queryset(self):
        clean_subquery = (
            CleanClothStock.objects.filter(cloth_stock=OuterRef("pk"))
            .values("cloth_stock")
            .annotate(total=Sum("total_length"))
            .values("total")
        )
        clean_cnt_subquery = (
            CleanClothStock.objects.filter(cloth_stock=OuterRef("pk"))
            .values("cloth_stock")
            .annotate(cnt=Count("id"))
            .values("cnt")
        )
        defected_subquery = (
            DefectedClothStock.objects.filter(cloth_stock=OuterRef("pk"))
            .values("cloth_stock")
            .annotate(total=Sum("total_length"))
            .values("total")
        )
        defected_cnt_subquery = (
            DefectedClothStock.objects.filter(cloth_stock=OuterRef("pk"))
            .values("cloth_stock")
            .annotate(cnt=Count("id"))
            .values("cnt")
        )

        return (
            ClothStock.objects
            .select_related("cloth_name", "created_by", "updated_by")
            .annotate(
                clean_record_count=Coalesce(Subquery(clean_cnt_subquery, output_field=IntegerField()), 0),
                defected_total_length=Coalesce(
                    Subquery(defected_subquery, output_field=DecimalField(max_digits=15, decimal_places=6)),
                    Decimal("0.000000"),
                ),
                defected_record_count=Coalesce(Subquery(defected_cnt_subquery, output_field=IntegerField()), 0),
            )
            .order_by("cloth_name__name")
        )

    serializer_class = ClothStockSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def create(self, request, *args, **kwargs):
        # Allow creating ClothStock directly if cloth_name is provided
        cn_id = request.data.get("cloth_name") or request.data.get("cloth_name_id") or request.data.get("clothNameId")
        if not cn_id:
            raise ValidationError({"cloth_name": ["cloth_name is required."]})
        try:
            cloth_name = ClothName.objects.get(id=cn_id)
        except ClothName.DoesNotExist:
            raise ValidationError({"cloth_name": [f"ClothName #{cn_id} does not exist."]})

        stock, created = ClothStock.objects.get_or_create(
            cloth_name=cloth_name,
            defaults={
                "total_length": Decimal("0.000000"),
                "created_by": request.user,
                "updated_by": request.user,
            }
        )
        sync_cloth_stock_clean_total(stock)
        obj = self.get_queryset().get(id=stock.id)
        serializer = self.get_serializer(obj, context={"request": request})
        return Response({
            "success": True,
            "message": f"Cloth stock for '{cloth_name.name}' {'created' if created else 'retrieved'} successfully.",
            "data": serializer.data,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.clean_records.exists() or instance.defected_records.exists() or instance.total_length > Decimal("0"):
            raise ValidationError({
                "detail": f"Cannot delete ClothStock for '{instance.cloth_name.name}' because it contains clean or defected stock records."
            })
        name = instance.cloth_name.name
        instance.delete()
        return Response({
            "success": True,
            "message": f"Cloth stock for '{name}' deleted successfully.",
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="recalculate")
    def recalculate(self, request, pk=None):
        instance = self.get_object()
        sync_cloth_stock_clean_total(instance)
        refreshed = self.get_queryset().get(id=instance.id)
        serializer = self.get_serializer(refreshed, context={"request": request})
        return Response({
            "success": True,
            "message": f"Cloth stock for '{instance.cloth_name.name}' synchronized successfully.",
            "data": serializer.data,
        })


class CleanClothStockViewSet(ModelViewSet):
    """
    CRUD API for individual CleanClothStock records.
    Filters by cloth_stock, cloth_patch, stock_date, etc.
    """
    queryset = (
        CleanClothStock.objects
        .select_related(
            "cloth_stock",
            "cloth_stock__cloth_name",
            "cloth_patch",
            "cloth_patch__beam_loading__sizing_outcome",
            "created_by",
            "updated_by",
        )
        .all()
    )
    serializer_class = CleanClothStockSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CleanClothStockFilter
    search_fields = [
        "cloth_patch__patch_number",
        "cloth_patch__beam_loading__sizing_outcome__set_no",
        "cloth_stock__cloth_name__name",
        "remarks",
    ]
    ordering_fields = [
        "stock_date",
        "total_length",
        "cloth_patch__patch_number",
        "cloth_stock__cloth_name__name",
        "created_at",
        "id",
    ]
    ordering = ["-stock_date", "-id"]

    permission_map = {
        "GET": "stock.view",
        "POST": "stock.manage",
        "PUT": "stock.manage",
        "PATCH": "stock.manage",
        "DELETE": "stock.manage",
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        out = CleanClothStockSerializer(instance, context={"request": request})
        return Response({
            "success": True,
            "message": f"Clean cloth stock ({instance.total_length}m) allocated successfully.",
            "data": out.data,
        }, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        out = CleanClothStockSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": f"Clean cloth stock record updated successfully.",
            "data": out.data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        rec_id = instance.id
        delete_clean_cloth_stock(instance, user=request.user, request=request)
        return Response({
            "success": True,
            "message": f"Clean cloth stock record #{rec_id} deleted successfully.",
        }, status=status.HTTP_200_OK)


class DefectedClothStockViewSet(ModelViewSet):
    """
    CRUD API for individual DefectedClothStock records.
    Filters by cloth_stock, cloth_patch, defect_type, stock_date, etc.
    """
    queryset = (
        DefectedClothStock.objects
        .select_related(
            "cloth_stock",
            "cloth_stock__cloth_name",
            "cloth_patch",
            "cloth_patch__beam_loading__sizing_outcome",
            "created_by",
            "updated_by",
        )
        .all()
    )
    serializer_class = DefectedClothStockSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DefectedClothStockFilter
    search_fields = [
        "defect_type",
        "defect_description",
        "cloth_patch__patch_number",
        "cloth_patch__beam_loading__sizing_outcome__set_no",
        "cloth_stock__cloth_name__name",
        "remarks",
    ]
    ordering_fields = [
        "stock_date",
        "total_length",
        "defect_type",
        "cloth_patch__patch_number",
        "cloth_stock__cloth_name__name",
        "created_at",
        "id",
    ]
    ordering = ["-stock_date", "-id"]

    permission_map = {
        "GET": "stock.view",
        "POST": "stock.manage",
        "PUT": "stock.manage",
        "PATCH": "stock.manage",
        "DELETE": "stock.manage",
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        out = DefectedClothStockSerializer(instance, context={"request": request})
        return Response({
            "success": True,
            "message": f"Defected cloth stock ({instance.defect_type}: {instance.total_length}m) recorded successfully.",
            "data": out.data,
        }, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        out = DefectedClothStockSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": f"Defected cloth stock record updated successfully.",
            "data": out.data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        rec_id = instance.id
        delete_defected_cloth_stock(instance, user=request.user, request=request)
        return Response({
            "success": True,
            "message": f"Defected cloth stock record #{rec_id} deleted successfully.",
        }, status=status.HTTP_200_OK)
