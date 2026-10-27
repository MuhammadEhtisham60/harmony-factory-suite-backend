"""
Views for B-Grade Yarn.
Provides full CRUD via ModelViewSet and a Quality-Wise aggregated action just like YarnStock.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Max
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import BGradeYarn
from .serializers import BGradeYarnSerializer, BGradeYarnQualityWiseSerializer
from .filters import BGradeYarnFilter
from factory.yarn.yarn_intake.models import YarnOutcomeBGradeItem


class BGradeYarnViewSet(ModelViewSet):
    """
    CRUD ModelViewSet for B-Grade Yarn.

    Endpoints:
        GET    /api/v1/b-grade-yarn/              – List paginated entries
        POST   /api/v1/b-grade-yarn/              – Create B-grade yarn entry
        GET    /api/v1/b-grade-yarn/{id}/         – Retrieve single entry
        PUT    /api/v1/b-grade-yarn/{id}/         – Full update
        PATCH  /api/v1/b-grade-yarn/{id}/         – Partial update
        DELETE /api/v1/b-grade-yarn/{id}/         – Delete entry
        GET    /api/v1/b-grade-yarn/quality-wise/ – Aggregated quality-wise stock pools (like yarn-stock)
    """
    queryset = (
        BGradeYarn.objects
        .select_related("yarn_name", "yarn_type", "yarn_count", "created_by", "updated_by")
        .all()
    )
    serializer_class = BGradeYarnSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BGradeYarnFilter
    search_fields = [
        "yarn_name__name",
        "yarn_type__name",
        "yarn_count__name",
        "lot_number",
        "production_type",
        "remarks",
    ]
    ordering_fields = [
        "yarn_name__name",
        "yarn_type__name",
        "yarn_count__name",
        "production_type",
        "cones",
        "weight_kg",
        "weight_lb",
        "entry_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-entry_date", "-id"]

    permission_map = {
        "GET": ["b_grade_yarn.view", "yarn_stock.view", "yarn_intake.view", "yarn.view"],
        "POST": ["b_grade_yarn.add", "yarn_stock.edit", "yarn_intake.add", "yarn.add"],
        "PUT": ["b_grade_yarn.edit", "yarn_stock.edit", "yarn_intake.edit", "yarn.edit"],
        "PATCH": ["b_grade_yarn.edit", "yarn_stock.edit", "yarn_intake.edit", "yarn.edit"],
        "DELETE": ["b_grade_yarn.delete", "yarn_stock.edit", "yarn_intake.delete", "yarn.delete"],
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create B-Grade Yarn",
            description=f"Created B-grade yarn entry '{instance.yarn_name.name} {instance.yarn_count.name}' ({instance.cones} cones, {instance.weight_kg} kg).",
            module="B-Grade Yarn",
            status="Success",
        )
        return Response(
            {"success": True, "message": "B-Grade yarn created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update B-Grade Yarn",
            description=f"Updated B-grade yarn entry #{updated.id} '{updated.yarn_name.name} {updated.yarn_count.name}'.",
            module="B-Grade Yarn",
            status="Success",
        )
        return Response(
            {"success": True, "message": "B-Grade yarn updated successfully.", "data": serializer.data}
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        desc = f"B-grade yarn #{instance.id} '{instance.yarn_name.name} {instance.yarn_count.name}'"
        instance.delete()

        log_activity(
            request=request,
            action="Delete B-Grade Yarn",
            description=f"Deleted {desc}.",
            module="B-Grade Yarn",
            status="Success",
        )
        return Response(
            {"success": True, "message": "B-Grade yarn deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="quality-wise")
    def quality_wise(self, request):
        """
        Returns aggregated quality-wise B-grade yarn pools, matching yarn-stock table.
        Groups by (yarn_name, yarn_type, yarn_count, production_type).
        Boxes and price are completely omitted.
        """
        filtered_qs = self.filter_queryset(self.get_queryset())

        # Grouping aggregation
        grouped = (
            filtered_qs
            .values("yarn_name_id", "yarn_name__name", "yarn_type_id", "yarn_type__name", "yarn_count_id", "yarn_count__name", "production_type")
            .annotate(
                total_cones=Sum("cones"),
                total_weight_kg=Sum("weight_kg"),
                total_weight_lb=Sum("weight_lb"),
                entries_count=Count("id"),
                last_updated=Max("updated_at"),
            )
            .order_by("yarn_name__name", "yarn_count__name", "production_type")
        )

        results = []
        for idx, row in enumerate(grouped, start=1):
            w_kg = Decimal(str(row["total_weight_kg"] or 0))
            w_lb = Decimal(str(row["total_weight_lb"] or 0))
            cones = int(row["total_cones"] or 0)
            is_in_stock = cones > 0 or w_kg > 0

            # Gather lot numbers for this quality
            lots = list(
                filtered_qs
                .filter(
                    yarn_name_id=row["yarn_name_id"],
                    yarn_type_id=row["yarn_type_id"],
                    yarn_count_id=row["yarn_count_id"],
                    production_type=row["production_type"],
                )
                .exclude(lot_number="")
                .values_list("lot_number", flat=True)
                .distinct()
            )

            # Total dispatched cones for this quality pool (net dispatched: dispatched - returned)
            disp_agg = (
                YarnOutcomeBGradeItem.objects
                .filter(
                    b_grade_yarn__yarn_name_id=row["yarn_name_id"],
                    b_grade_yarn__yarn_type_id=row["yarn_type_id"],
                    b_grade_yarn__yarn_count_id=row["yarn_count_id"],
                    b_grade_yarn__production_type=row["production_type"],
                )
                .aggregate(
                    total=Sum("cones"),
                    returned=Sum("returned_cones"),
                )
            )
            tot_disp = disp_agg["total"] or 0
            tot_ret = disp_agg["returned"] or 0
            dispatched_cones = max(0, tot_disp - tot_ret)

            # Synthesize quality key ID
            quality_key = f"{row['yarn_name_id']}-{row['yarn_type_id']}-{row['yarn_count_id']}-{row['production_type'] or 'default'}"

            results.append({
                "id": quality_key,
                "yarnName": row["yarn_name__name"],
                "yarnType": row["yarn_type__name"],
                "yarnCount": row["yarn_count__name"],
                "yarnNameId": row["yarn_name_id"],
                "yarnTypeId": row["yarn_type_id"],
                "yarnCountId": row["yarn_count_id"],
                "productionType": row["production_type"] or "Self",
                "totalCones": cones,
                "totalDispatchedCones": dispatched_cones,
                "totalReturnedCones": tot_ret,
                "grossDispatchedCones": tot_disp,
                "totalWeightKg": str(w_kg.quantize(Decimal("0.0001"))),
                "totalWeightLb": str(w_lb.quantize(Decimal("0.0001"))),
                "entriesCount": row["entries_count"],
                "lotNumbers": lots,
                "lastUpdated": row["last_updated"],
                "status": "In Stock" if is_in_stock else "Depleted",
            })

        # Calculate overall view totals
        summary_totals = {
            "totalQualities": len(results),
            "totalCones": sum(r["totalCones"] for r in results),
            "totalWeightKg": sum(Decimal(r["totalWeightKg"]) for r in results),
            "totalWeightLb": sum(Decimal(r["totalWeightLb"]) for r in results),
        }

        # Optional pagination if requested
        page = self.paginate_queryset(results)
        if page is not None:
            serializer = BGradeYarnQualityWiseSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["summary"] = summary_totals
            return response

        serializer = BGradeYarnQualityWiseSerializer(results, many=True)
        return Response({
            "success": True,
            "count": len(results),
            "summary": summary_totals,
            "results": serializer.data,
        })
