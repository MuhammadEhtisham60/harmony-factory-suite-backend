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

from django.db import models
from rest_framework.exceptions import PermissionDenied

from factory.yarn.sizing.models import SizingOutcome
from factory.yarn.sizing.serializers import SizingOutcomeSerializer
from factory.yarn.sizing.views import SizingOutcomeViewSet
from factory.yarn.sizing.services import sync_yarn_outcome_status, sync_sizing_outcome_to_intake
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


class WarpingOutcomeViewSet(SizingOutcomeViewSet):
    """
    CRUD for Warping Outcome (returned set from warping unit) and Beam assignment.

    Endpoints:
        GET    /warping-outcomes/                   – list warping outcomes
        POST   /warping-outcomes/                   – create warping outcome & assign beams
        GET    /warping-outcomes/{id}/              – retrieve warping outcome detail
        PUT    /warping-outcomes/{id}/              – update warping outcome
        PATCH  /warping-outcomes/{id}/              – partial update
        DELETE /warping-outcomes/{id}/              – delete warping outcome
        POST   /warping-outcomes/{id}/assign-beams/ – assign additional beams
        GET    /warping-outcomes/{id}/beams/        – list assigned beams
        POST   /warping-outcomes/{id}/release-beam/ – release a beam
    """

    permission_map = {
        "GET": ("warping.view", "sizing.view"),
        "POST": ("warping.add", "sizing.add"),
        "PUT": ("warping.edit", "sizing.edit"),
        "PATCH": ("warping.edit", "sizing.edit"),
        "DELETE": ("warping.delete", "sizing.delete"),
    }

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(
            models.Q(yarn_outcome__outcome_type="Warping")
            | models.Q(yarn_outcome__warping__isnull=False)
        )

    def create(self, request, *args, **kwargs):
        raw_beams = request.data.get("beam_ids") or request.data.get("beamIds")
        if raw_beams:
            if not request.user.is_superuser and not (
                request.user.has_perm_code("beams.assign")
                or request.user.has_perm_code("warping.add")
                or request.user.has_perm_code("sizing.add")
            ):
                raise PermissionDenied("You do not have permission to assign beams.")

        serializer = SizingOutcomeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        outcome = serializer.save()

        refreshed = (
            SizingOutcome.objects
            .select_related("yarn_outcome", "yarn_outcome__sizing", "yarn_outcome__warping", "created_by", "updated_by")
            .get(id=outcome.id)
        )
        out = SizingOutcomeSerializer(refreshed, context={"request": request})
        return Response(
            {
                "success": True,
                "message": f"Warping outcome #{outcome.id} created successfully with {outcome.total_beams} beam(s).",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SizingOutcomeSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        if updated.yarn_outcome:
            sync_yarn_outcome_status(updated.yarn_outcome)
            sync_sizing_outcome_to_intake(updated.yarn_outcome)

        log_activity(
            request=request,
            action="Update Warping Outcome",
            description=f"Updated Warping Outcome #{updated.id}.",
            module="Yarn – Warping",
            status="Success",
        )
        return Response({
            "success": True,
            "message": "Warping outcome updated successfully.",
            "data": SizingOutcomeSerializer(updated, context={"request": request}).data,
        })

    @action(detail=True, methods=["post"], url_path="assign-beams")
    def assign_beams(self, request, pk=None):
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("warping.edit")
            or request.user.has_perm_code("sizing.edit")
        ):
            raise PermissionDenied("You do not have permission to assign beams.")
        return super().assign_beams(request, pk)

    @action(detail=True, methods=["post"], url_path="release-beam")
    def release_beam(self, request, pk=None):
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("beams.edit")
            or request.user.has_perm_code("warping.edit")
            or request.user.has_perm_code("sizing.edit")
        ):
            raise PermissionDenied("You do not have permission to release beams.")
        return super().release_beam(request, pk)


