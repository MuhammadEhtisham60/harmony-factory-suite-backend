"""
Views for the Beam module – full CRUD via ModelViewSet.
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

from .models import Beam
from .serializers import BeamListSerializer, BeamDetailSerializer
from .filters import BeamFilter


class BeamViewSet(ModelViewSet):
    """
    ModelViewSet for Beam CRUD operations.

    Endpoints (router-generated):
        GET    /beams/            – list   (paginated, filterable)
        POST   /beams/            – create
        GET    /beams/{id}/       – retrieve
        PUT    /beams/{id}/       – full update
        PATCH  /beams/{id}/       – partial update
        DELETE /beams/{id}/       – destroy
        GET    /beams/stats/      – aggregate counts by status
        GET    /beams/choices/    – dropdown option lists
    """

    queryset = (
        Beam.objects
        .select_related("created_by", "updated_by")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BeamFilter
    search_fields = [
        "beam_code",
        "beam_name",
        "beam_number",
        "yarn_count",
        "production_order",
    ]
    ordering_fields = [
        "beam_code",
        "beam_name",
        "beam_number",
        "status",
        "yarn_count",
        "length",
        "weight",
        "warp_count",
        "total_ends",
        "created_at",
        "updated_at",
    ]
    ordering = ["beam_code"]

    # RBAC permission map
    permission_map = {
        "GET": "beams.view",
        "POST": "beams.add",
        "PUT": "beams.change",
        "PATCH": "beams.change",
        "DELETE": "beams.delete",
    }

    # ------------------------------------------------------------------ #
    # Serializer selection
    # ------------------------------------------------------------------ #

    def get_serializer_class(self):
        if self.action == "list":
            return BeamListSerializer
        return BeamDetailSerializer

    # ------------------------------------------------------------------ #
    # CRUD overrides – consistent response shape + audit logging
    # ------------------------------------------------------------------ #

    def create(self, request, *args, **kwargs):
        serializer = BeamDetailSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Beam",
            description=(
                f"Created beam '{instance.beam_number}' (Code: {instance.beam_code})."
            ),
            module="Factory – Beams",
            status="Success",
        )

        out = BeamDetailSerializer(instance, context={"request": request})
        return Response(
            {
                "success": True,
                "message": "Beam created successfully.",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = BeamDetailSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = BeamDetailSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Beam",
            description=(
                f"Updated beam '{updated.beam_number}' (Code: {updated.beam_code},"
                f" Status: {updated.status})."
            ),
            module="Factory – Beams",
            status="Success",
        )

        out = BeamDetailSerializer(updated, context={"request": request})
        return Response(
            {
                "success": True,
                "message": "Beam updated successfully.",
                "data": out.data,
            }
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        beam_code = instance.beam_code
        beam_number = instance.beam_number
        instance.delete()

        log_activity(
            request=request,
            action="Delete Beam",
            description=(
                f"Deleted beam '{beam_number}' (Code: {beam_code})."
            ),
            module="Factory – Beams",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Beam deleted successfully."},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------ #
    # Custom actions
    # ------------------------------------------------------------------ #

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        Returns aggregate counts:
            totalBeams
            byStatus : {Available: n, Sizing: n, Loaded: n, ...}
        """
        qs = self.filter_queryset(self.get_queryset())

        by_status = {
            v: qs.filter(status=v).count()
            for v, _ in Beam.StatusChoices.choices
        }

        return Response(
            {
                "success": True,
                "data": {
                    "totalBeams": qs.count(),
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
                        for v, l in Beam.StatusChoices.choices
                    ],
                },
            }
        )
