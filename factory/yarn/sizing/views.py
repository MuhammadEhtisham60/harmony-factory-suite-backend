"""
Views for Sizing, SizingOutcome, and SizingBeamAssignment.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.exceptions import PermissionDenied

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from factory.beam.models import Beam
from .models import Sizing, SizingOutcome, SizingBeamAssignment
from .serializers import (
    SizingSerializer,
    SizingOutcomeSerializer,
    SizingBeamAssignmentSerializer,
    AssignBeamsSerializer,
    ReleaseBeamRequestSerializer,
    TransitionAssignmentSerializer,
    BeamMinSerializer,
)
from .filters import SizingFilter, SizingOutcomeFilter, SizingBeamAssignmentFilter
from .services import (
    assign_beams_to_outcome,
    transition_beam_assignment,
    release_beam_assignment,
)


class SizingViewSet(ModelViewSet):
    """
    CRUD for Sizing units.

    Endpoints:
        GET    /sizings/
        POST   /sizings/
        GET    /sizings/{id}/
        PUT    /sizings/{id}/
        PATCH  /sizings/{id}/
        DELETE /sizings/{id}/
        GET    /sizings/choices/      → dropdown list for forms
        GET    /sizings/{id}/outcomes/ → list all outcomes for this sizing unit
    """

    queryset = (
        Sizing.objects
        .select_related("created_by", "updated_by")
        .all()
    )
    serializer_class = SizingSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SizingFilter
    search_fields = ["sizing_name", "contact_person", "phone_no", "email"]
    ordering_fields = ["sizing_name", "status", "created_at", "updated_at"]
    ordering = ["sizing_name"]

    permission_map = {
        "GET": "sizing.view",
        "POST": "sizing.add",
        "PUT": "sizing.edit",
        "PATCH": "sizing.edit",
        "DELETE": "sizing.delete",
    }

    def create(self, request, *args, **kwargs):
        serializer = SizingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Sizing",
            description=f"Created sizing '{instance.sizing_name}'.",
            module="Yarn – Sizing",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Sizing created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = SizingSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SizingSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Sizing",
            description=f"Updated sizing '{updated.sizing_name}'.",
            module="Yarn – Sizing",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Sizing updated successfully.", "data": serializer.data}
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.sizing_name
        instance.delete()

        log_activity(
            request=request,
            action="Delete Sizing",
            description=f"Deleted sizing '{name}'.",
            module="Yarn – Sizing",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Sizing deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """Returns active sizings as a minimal list for dropdowns."""
        sizings = Sizing.objects.filter(status="Active").values("id", "sizing_name", "contact_person")
        return Response({
            "success": True,
            "data": [
                {"value": s["id"], "label": s["sizing_name"], "contactPerson": s["contact_person"]}
                for s in sizings
            ]
        })

    @action(detail=True, methods=["get"], url_path="outcomes")
    def outcomes(self, request, pk=None):
        """Returns all SizingOutcome records for this Sizing unit."""
        sizing = self.get_object()
        qs = (
            SizingOutcome.objects
            .filter(sizing=sizing)
            .select_related("sizing", "created_by", "updated_by")
            .prefetch_related(
                "beam_assignments",
                "beam_assignments__beam",
                "beam_assignments__created_by",
                "beam_assignments__updated_by",
            )
            .order_by("-outcome_date", "-id")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SizingOutcomeSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = SizingOutcomeSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class SizingOutcomeViewSet(ModelViewSet):
    """
    CRUD for SizingOutcome and Beam assignment.

    Endpoints:
        GET    /sizing-outcomes/              – list (filterable by sizing, outcome_date, etc.)
        POST   /sizing-outcomes/              – create outcome, optionally assigns beams
        GET    /sizing-outcomes/{id}/         – retrieve outcome detail with assigned beams
        PUT    /sizing-outcomes/{id}/         – update outcome remarks/date
        PATCH  /sizing-outcomes/{id}/         – partial update
        DELETE /sizing-outcomes/{id}/         – delete outcome
        POST   /sizing-outcomes/{id}/assign-beams/ – assign additional existing beams
        GET    /sizing-outcomes/{id}/beams/   – list all beams assigned to this outcome
        POST   /sizing-outcomes/{id}/release-beam/ – release a beam from this outcome
    """

    queryset = (
        SizingOutcome.objects
        .select_related("sizing", "created_by", "updated_by")
        .prefetch_related(
            "beam_assignments",
            "beam_assignments__beam",
            "beam_assignments__created_by",
            "beam_assignments__updated_by",
        )
        .all()
    )
    serializer_class = SizingOutcomeSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SizingOutcomeFilter
    search_fields = ["sizing__sizing_name", "sizing__contact_person", "remarks"]
    ordering_fields = ["outcome_date", "created_at", "updated_at"]
    ordering = ["-outcome_date", "-id"]

    permission_map = {
        "GET": "sizing.view",
        "POST": "sizing.add",
        "PUT": "sizing.edit",
        "PATCH": "sizing.edit",
        "DELETE": "sizing.delete",
    }

    def create(self, request, *args, **kwargs):
        # If user is assigning beams during creation, check beams.assign or sizing.add
        raw_beams = request.data.get("beam_ids") or request.data.get("beamIds")
        if raw_beams:
            if not request.user.is_superuser and not (
                request.user.has_perm_code("beams.assign")
                or request.user.has_perm_code("sizing.add")
            ):
                raise PermissionDenied("You do not have permission to assign beams.")

        serializer = SizingOutcomeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        outcome = serializer.save()

        # Reload with prefetched assignments for response
        refreshed = (
            SizingOutcome.objects
            .select_related("sizing", "created_by", "updated_by")
            .prefetch_related("beam_assignments__beam")
            .get(id=outcome.id)
        )
        out = SizingOutcomeSerializer(refreshed, context={"request": request})
        return Response(
            {
                "success": True,
                "message": f"Sizing outcome #{outcome.id} created successfully with {outcome.total_beams} beam(s).",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = SizingOutcomeSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SizingOutcomeSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Sizing Outcome",
            description=f"Updated Sizing Outcome #{updated.id}.",
            module="Yarn – Sizing",
            status="Success",
        )
        return Response({
            "success": True,
            "message": "Sizing outcome updated successfully.",
            "data": SizingOutcomeSerializer(updated, context={"request": request}).data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        oid = instance.id

        # Check if there are active assignments
        active_assignments = instance.beam_assignments.filter(
            status__in=[
                SizingBeamAssignment.StatusChoices.ASSIGNED,
                SizingBeamAssignment.StatusChoices.IN_USE,
            ]
        )
        if active_assignments.exists():
            return Response(
                {
                    "success": False,
                    "message": "Cannot delete sizing outcome with active beam assignments. Release or complete assignments first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.delete()
        log_activity(
            request=request,
            action="Delete Sizing Outcome",
            description=f"Deleted Sizing Outcome #{oid}.",
            module="Yarn – Sizing",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Sizing outcome deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="assign-beams")
    def assign_beams(self, request, pk=None):
        """
        Assigns additional existing Beams to this SizingOutcome.
        Payload:
            { "beam_ids": [101, 102] } or { "beamIds": [101, 102] }
        """
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("sizing.edit")
        ):
            raise PermissionDenied("You do not have permission to assign beams.")

        outcome = self.get_object()
        serializer = AssignBeamsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        beam_ids = serializer.validated_data["beam_ids"]
        created_assignments = assign_beams_to_outcome(
            sizing_outcome=outcome,
            beam_ids=beam_ids,
            user=request.user,
            request=request,
        )

        out_serializer = SizingBeamAssignmentSerializer(
            created_assignments, many=True, context={"request": request}
        )
        total_assigned = SizingBeamAssignment.objects.filter(sizing_outcome=outcome).count()
        return Response(
            {
                "success": True,
                "message": f"Successfully assigned {len(created_assignments)} beam(s) to Sizing Outcome #{outcome.id}.",
                "data": {
                    "sizingOutcomeId": outcome.id,
                    "totalBeamsAssigned": total_assigned,
                    "assignments": out_serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="beams")
    def beams(self, request, pk=None):
        """Lists all Beams assigned to this SizingOutcome."""
        outcome = self.get_object()
        assignments = (
            outcome.beam_assignments
            .select_related("beam", "created_by", "updated_by")
            .all()
        )
        serializer = SizingBeamAssignmentSerializer(assignments, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": {
                "sizingOutcomeId": outcome.id,
                "outcomeDate": outcome.outcome_date,
                "totalBeams": assignments.count(),
                "assignments": serializer.data,
            }
        })

    @action(detail=True, methods=["post"], url_path="release-beam")
    def release_beam(self, request, pk=None):
        """
        Releases a specific assigned Beam from this SizingOutcome.
        Payload:
            { "beam_id": 101 } or { "assignment_id": 55 }
        """
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("beams.edit")
        ):
            raise PermissionDenied("You do not have permission to release beams.")

        outcome = self.get_object()
        req_serializer = ReleaseBeamRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)

        bid = req_serializer.validated_data.get("resolved_beam_id")
        aid = req_serializer.validated_data.get("resolved_assignment_id")

        if aid:
            assignment = outcome.beam_assignments.filter(id=aid).first()
        else:
            assignment = outcome.beam_assignments.filter(
                beam_id=bid,
            ).exclude(status=SizingBeamAssignment.StatusChoices.RELEASED).first()

        if not assignment:
            return Response(
                {
                    "success": False,
                    "message": "No matching active/unreleased assignment found in this sizing outcome.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        released = release_beam_assignment(
            assignment=assignment,
            user=request.user,
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Beam '{released.beam.beam_number}' has been released and is now Available.",
            "data": SizingBeamAssignmentSerializer(released, context={"request": request}).data,
        })


class SizingBeamAssignmentViewSet(ReadOnlyModelViewSet):
    """
    ViewSet for viewing, transitioning, and releasing Beam Sizing Assignments.

    Endpoints:
        GET    /sizing-beam-assignments/       – list all assignments (filter by beam, outcome, status)
        GET    /sizing-beam-assignments/{id}/  – get assignment detail
        POST   /sizing-beam-assignments/{id}/transition/ – transition assignment status
        POST   /sizing-beam-assignments/{id}/release/    – release assignment & make beam Available
    """

    queryset = (
        SizingBeamAssignment.objects
        .select_related("beam", "sizing_outcome", "sizing_outcome__sizing", "created_by", "updated_by")
        .all()
    )
    serializer_class = SizingBeamAssignmentSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SizingBeamAssignmentFilter
    search_fields = ["beam__beam_number", "sizing_outcome__sizing__sizing_name"]
    ordering_fields = ["assigned_at", "released_at", "status"]
    ordering = ["-assigned_at", "-id"]

    permission_map = {
        "GET": "beams.view",
        "POST": "beams.assign",
        "PUT": "beams.edit",
        "PATCH": "beams.edit",
        "DELETE": "beams.delete",
    }

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        """
        Transitions assignment status (e.g. IN_USE, COMPLETED, RELEASED).
        Payload:
            { "status": "IN_USE" }
        """
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("beams.edit")
        ):
            raise PermissionDenied("You do not have permission to transition beam assignments.")

        assignment = self.get_object()
        req_serializer = TransitionAssignmentSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)

        new_status = req_serializer.validated_data["status"]
        updated = transition_beam_assignment(
            assignment=assignment,
            new_status=new_status,
            user=request.user,
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Assignment #{updated.id} transitioned to '{new_status}'.",
            "data": SizingBeamAssignmentSerializer(updated, context={"request": request}).data,
        })

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        """
        Releases this assignment, sets released_at, and marks physical Beam as AVAILABLE.
        """
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("beams.edit")
        ):
            raise PermissionDenied("You do not have permission to release beam assignments.")

        assignment = self.get_object()
        released = release_beam_assignment(
            assignment=assignment,
            user=request.user,
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Beam '{released.beam.beam_number}' released and marked Available.",
            "data": SizingBeamAssignmentSerializer(released, context={"request": request}).data,
        })
