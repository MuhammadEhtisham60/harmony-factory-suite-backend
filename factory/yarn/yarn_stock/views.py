"""
Views for the YarnStock module.
Provides listing, filtering, detail, contributing intakes, and outcome history.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .filters import YarnStockFilter
from .models import YarnStock
from .serializers import (
    YarnStockDetailSerializer,
    YarnStockListSerializer,
)
from .services import recalculate_yarn_stock, reconcile_all_stocks


class YarnStockPermission(HasERPModulePermission):
    """
    Grants access if user has yarn_stock or yarn_intake permissions.
    Ensures seamless backward compatibility.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if request.user.status != "Active":
            return False
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return (
                request.user.has_perm_code("yarn_stock.view")
                or request.user.has_perm_code("yarn_intake.view")
            )
        return (
            request.user.has_perm_code("yarn_stock.edit")
            or request.user.has_perm_code("yarn_intake.edit")
        )


class YarnStockViewSet(ReadOnlyModelViewSet):
    """
    Shared yarn stock pools API.

    GET  /yarn-stocks/              → Paginated list of shared stock pools
    GET  /yarn-stocks/{id}/         → Detail of a stock pool
    GET  /yarn-stocks/{id}/intakes/  → List of intakes contributing to this pool
    GET  /yarn-stocks/{id}/outcomes/ → List of outcomes deducted from this pool
    POST /yarn-stocks/{id}/reconcile/ → Manually reconcile stock from ledger
    POST /yarn-stocks/reconcile-all/  → Reconcile all stock pools
    """

    queryset = (
        YarnStock.objects
        .select_related("yarn_name", "yarn_type", "yarn_count", "created_by", "updated_by")
        .prefetch_related("intakes", "outcomes")
        .all()
    )
    serializer_class = YarnStockListSerializer
    permission_classes = [IsAuthenticated, YarnStockPermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnStockFilter
    search_fields = [
        "yarn_name__name",
        "yarn_type__name",
        "yarn_count__name",
        "production_type",
    ]
    ordering_fields = [
        "yarn_name__name",
        "yarn_type__name",
        "yarn_count__name",
        "production_type",
        "total_boxes",
        "cones",
        "total_weight_kg",
        "total_weight_lb",
        "price",
        "total_price",
        "created_at",
        "updated_at",
    ]
    ordering = ["yarn_name__name", "yarn_count__name", "-id"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return YarnStockDetailSerializer
        return YarnStockListSerializer

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "data": serializer.data
        })

    @action(detail=True, methods=["get"], url_path="intakes")
    def intakes(self, request, pk=None):
        """
        Returns all YarnIntake records contributing to this stock pool.
        """
        from factory.yarn.yarn_intake.serializers import YarnIntakeListSerializer
        stock = self.get_object()
        intakes = (
            stock.intakes
            .select_related("supplier", "created_by", "updated_by")
            .all()
            .order_by("-intake_date", "-id")
        )

        page = self.paginate_queryset(intakes)
        if page is not None:
            serializer = YarnIntakeListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = YarnIntakeListSerializer(intakes, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data
        })

    @action(detail=True, methods=["get"], url_path="outcomes")
    def outcomes(self, request, pk=None):
        """
        Returns all YarnOutcome records dispatched from this stock pool.
        """
        from factory.yarn.yarn_intake.serializers import YarnOutcomeSerializer
        stock = self.get_object()
        outcomes = (
            stock.outcomes
            .select_related("yarn_buyer", "sizing", "created_by", "updated_by")
            .all()
            .order_by("-outcome_date", "-id")
        )

        page = self.paginate_queryset(outcomes)
        if page is not None:
            serializer = YarnOutcomeSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = YarnOutcomeSerializer(outcomes, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data
        })

    @action(detail=True, methods=["post"], url_path="reconcile")
    def reconcile(self, request, pk=None):
        """
        Forces recalculation of this stock pool from source records.
        """
        stock = self.get_object()
        recalculate_yarn_stock(stock)

        log_activity(
            request=request,
            action="Reconcile Yarn Stock",
            description=f"Reconciled stock pool #{stock.id} ({stock.yarn_name.name if stock.yarn_name else ''} {stock.yarn_count.name if stock.yarn_count else ''}).",
            module="Yarn – Stock",
            status="Success",
        )

        serializer = YarnStockDetailSerializer(stock, context={"request": request})
        return Response({
            "success": True,
            "message": "Stock reconciled successfully.",
            "data": serializer.data
        })

    @action(detail=False, methods=["post"], url_path="reconcile-all")
    def reconcile_all(self, request):
        """
        Forces recalculation of all stock pools.
        """
        count = reconcile_all_stocks()
        log_activity(
            request=request,
            action="Reconcile All Yarn Stocks",
            description=f"Reconciled all {count} yarn stock pools.",
            module="Yarn – Stock",
            status="Success",
        )
        return Response({
            "success": True,
            "message": f"Successfully reconciled {count} stock pool(s)."
        })
