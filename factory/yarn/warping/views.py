"""
Views for Warping master module.
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

from factory.yarn.sizing.models import SizingOutcome
from factory.yarn.sizing.serializers import SizingOutcomeSerializer
from .models import Warping
from .serializers import WarpingSerializer
from .filters import WarpingFilter


class WarpingViewSet(ModelViewSet):
    """
    CRUD for Warping units.

    Endpoints:
        GET    /warpings/
        POST   /warpings/
        GET    /warpings/{id}/
        PUT    /warpings/{id}/
        PATCH  /warpings/{id}/
        DELETE /warpings/{id}/
        GET    /warpings/choices/       → dropdown list for forms
        GET    /warpings/{id}/outcomes/ → list all outcomes for this warping unit
    """

    queryset = (
        Warping.objects
        .select_related("created_by", "updated_by")
        .all()
    )
    serializer_class = WarpingSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WarpingFilter
    search_fields = ["warping_name", "contact_person", "phone_no", "email"]
    ordering_fields = ["warping_name", "status", "created_at", "updated_at"]
    ordering = ["warping_name"]

    permission_map = {
        "GET": "warping.view",
        "POST": "warping.add",
        "PUT": "warping.edit",
        "PATCH": "warping.edit",
        "DELETE": "warping.delete",
    }

    def create(self, request, *args, **kwargs):
        serializer = WarpingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Warping",
            description=f"Created warping '{instance.warping_name}'.",
            module="Yarn – Warping",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Warping created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = WarpingSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = WarpingSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Warping",
            description=f"Updated warping '{updated.warping_name}'.",
            module="Yarn – Warping",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Warping updated successfully.", "data": serializer.data}
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.warping_name
        instance.delete()

        log_activity(
            request=request,
            action="Delete Warping",
            description=f"Deleted warping '{name}'.",
            module="Yarn – Warping",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Warping deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """Returns active warpings as a minimal list for dropdowns."""
        warpings = Warping.objects.filter(status="Active").values("id", "warping_name", "contact_person")
        return Response({
            "success": True,
            "data": [
                {"value": w["id"], "label": w["warping_name"], "contactPerson": w["contact_person"]}
                for w in warpings
            ]
        })

    @action(detail=True, methods=["get"], url_path="outcomes")
    def outcomes(self, request, pk=None):
        """Returns all SizingOutcome (returned sets) records for this Warping unit."""
        warping = self.get_object()
        qs = (
            SizingOutcome.objects
            .filter(yarn_outcome__warping=warping)
            .select_related("yarn_outcome", "yarn_outcome__warping", "created_by", "updated_by")
            .order_by("-outcome_date", "-id")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SizingOutcomeSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = SizingOutcomeSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})
