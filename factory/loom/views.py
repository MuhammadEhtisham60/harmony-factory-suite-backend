"""
Views for the Loom module – full CRUD via ModelViewSet.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import Loom
from .serializers import LoomListSerializer, LoomDetailSerializer
from .filters import LoomFilter


class LoomViewSet(ModelViewSet):
    """
    ModelViewSet for Loom CRUD operations.

    Endpoints (router-generated):
        GET    /looms/            – list   (paginated, filterable)
        POST   /looms/            – create
        GET    /looms/{id}/       – retrieve
        PUT    /looms/{id}/       – full update
        PATCH  /looms/{id}/       – partial update
        DELETE /looms/{id}/       – destroy
        GET    /looms/stats/      – aggregate counts by status
        GET    /looms/choices/    – dropdown option lists
    """

    queryset = (
        Loom.objects
        .select_related("created_by", "updated_by")
        .prefetch_related("beam_loadings", "beam_loadings__beam")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = LoomFilter
    search_fields = [
        "loom_code",
        "loom_name",
        "model_number",
        "location",
    ]
    ordering_fields = [
        "loom_code",
        "loom_name",
        "status",
        "location",
        "installation_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["loom_code"]

    # RBAC permission map
    permission_map = {
        "GET": "looms.view",
        "POST": "looms.add",
        "PUT": "looms.change",
        "PATCH": "looms.change",
        "DELETE": "looms.delete",
    }

    # ------------------------------------------------------------------ #
    # Serializer selection
    # ------------------------------------------------------------------ #

    def get_serializer_class(self):
        if self.action == "list":
            return LoomListSerializer
        return LoomDetailSerializer

    # ------------------------------------------------------------------ #
    # CRUD overrides – consistent response shape + audit logging
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        serializer = LoomDetailSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Loom",
            description=(
                f"Created loom '{instance.loom_name}' (Code: {instance.loom_code})."
            ),
            module="Factory – Looms",
            status="Success",
        )

        out = LoomDetailSerializer(instance, context={"request": request})
        return Response(
            {
                "success": True,
                "message": "Loom created successfully.",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = LoomDetailSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = LoomDetailSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Loom",
            description=(
                f"Updated loom '{updated.loom_name}' (Code: {updated.loom_code},"
                f" Status: {updated.status})."
            ),
            module="Factory – Looms",
            status="Success",
        )

        out = LoomDetailSerializer(updated, context={"request": request})
        return Response(
            {
                "success": True,
                "message": "Loom updated successfully.",
                "data": out.data,
            }
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        loom_code = instance.loom_code
        loom_name = instance.loom_name
        instance.delete()

        log_activity(
            request=request,
            action="Delete Loom",
            description=(
                f"Deleted loom '{loom_name}' (Code: {loom_code})."
            ),
            module="Factory – Looms",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Loom deleted successfully."},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------ #
    # Custom actions
    # ------------------------------------------------------------------ #

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        Returns aggregate counts:
            totalLooms
            byStatus : {Active: n, Inactive: n, Sizing: n, Production: n, Maintenance: n, Breakdown: n}
        """
        qs = self.filter_queryset(self.get_queryset())

        by_status = {
            v: qs.filter(status=v).count()
            for v, _ in Loom.StatusChoices.choices
        }

        return Response(
            {
                "success": True,
                "data": {
                    "totalLooms": qs.count(),
                    "byStatus": by_status,
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """
        Returns dropdown option lists for status.
        """
        return Response(
            {
                "success": True,
                "data": {
                    "statusChoices": [
                        {"value": v, "label": l}
                        for v, l in Loom.StatusChoices.choices
                    ],
                },
            }
        )
