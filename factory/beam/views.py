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

from .models import Beam, BeamLoading, Production
from .serializers import (
    BeamListSerializer,
    BeamDetailSerializer,
    BeamLoadingSerializer,
    BatchBeamLoadingSerializer,
    ProductionSerializer,
)
from .filters import BeamFilter, BeamLoadingFilter, ProductionFilter



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
        "beam_name",
        "beam_number",
        "yarn_count",
        "production_order",
    ]
    ordering_fields = [
        "beam_number",
        "beam_name",
        "status",
        "yarn_count",
        "length",
        "weight",
        "warp_count",
        "total_ends",
        "created_at",
        "updated_at",
    ]
    ordering = ["beam_number"]

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
                f"Created beam '{instance.beam_number}'."
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
                f"Updated beam '{updated.beam_number}' ("
                f"Status: {updated.status})."
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
        beam_number = instance.beam_number
        instance.delete()

        log_activity(
            request=request,
            action="Delete Beam",
            description=(
                f"Deleted beam '{beam_number}'."
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

    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        """
        Returns list of currently available beams ready for sizing assignment.
        """
        qs = (
            self.filter_queryset(self.get_queryset())
            .filter(status=Beam.StatusChoices.AVAILABLE)
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = BeamListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = BeamListSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    @action(detail=True, methods=["get"], url_path="sizing-history")
    def sizing_history(self, request, pk=None):
        """
        Returns the complete sizing history for this beam across all cycles.
        """
        beam = self.get_object()
        from factory.yarn.sizing.services import get_beam_sizing_history
        from factory.yarn.sizing.serializers import BeamAssignmentHistorySerializer

        history_qs = get_beam_sizing_history(beam.id)
        serializer = BeamAssignmentHistorySerializer(history_qs, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": {
                "beamId": beam.id,
                "beamNumber": beam.beam_number,
                "currentStatus": beam.status,
                "totalSizingCycles": history_qs.count(),
                "history": serializer.data,
            }
        })

    @action(detail=True, methods=["get"], url_path="active-assignment")
    def active_assignment(self, request, pk=None):
        """
        Returns the current active (ASSIGNED or IN_USE) sizing assignment of this beam, or null.
        """
        beam = self.get_object()
        from factory.yarn.sizing.services import get_beam_active_assignment
        from factory.yarn.sizing.serializers import SizingBeamAssignmentSerializer

        assignment = get_beam_active_assignment(beam.id)
        if not assignment:
            return Response({
                "success": True,
                "data": None,
                "message": f"Beam '{beam.beam_number}' has no active sizing assignment.",
            })

        serializer = SizingBeamAssignmentSerializer(assignment, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data,
        })

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        """
        Releases the beam's current active or unreleased sizing assignment when empty,
        marks the physical beam as Available, and preserves historical records.
        """
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("beams.edit")
        ):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to release beam assignments.")

        beam = self.get_object()
        from factory.yarn.sizing.services import release_beam_active_assignment
        from factory.yarn.sizing.serializers import SizingBeamAssignmentSerializer

        released_assignment = release_beam_active_assignment(
            beam_or_id=beam,
            user=request.user,
            request=request,
        )

        return Response({
            "success": True,
            "message": f"Beam '{beam.beam_number}' has been released and is now Available.",
            "data": SizingBeamAssignmentSerializer(released_assignment, context={"request": request}).data,
        })

    @action(detail=True, methods=["get"], url_path="loading-history")
    def loading_history(self, request, pk=None):
        """
        Returns the complete loading and loom history for this beam across all cycles.
        """
        beam = self.get_object()
        from .services import get_beam_loading_history
        loadings = get_beam_loading_history(beam.id)
        serializer = BeamLoadingSerializer(loadings, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": {
                "beamId": beam.id,
                "beamNumber": beam.beam_number,
                "currentStatus": beam.status,
                "totalLoadings": loadings.count(),
                "history": serializer.data,
            }
        })


class BeamLoadingViewSet(ModelViewSet):
    """
    ModelViewSet for BeamLoading operations.
    Represents: "Loading the returned Sizing Set onto an existing Beam and installing that Beam onto a Loom."

    Endpoints:
        GET    /beam-loadings/            – list (filterable by beam, loom, sizing_outcome, status)
        POST   /beam-loadings/            – create single loading (atomically locks Beam, verifies AVAILABLE, sets LOADED)
        POST   /beam-loadings/batch/      – batch load multiple beams for one SizingOutcome
        GET    /beam-loadings/{id}/       – retrieve
        PATCH  /beam-loadings/{id}/       – partial update
        DELETE /beam-loadings/{id}/       – delete (only if not yet In Production)
        POST   /beam-loadings/{id}/empty/ – mark beam as empty and AVAILABLE
        GET    /beam-loadings/active/     – list active (Loaded / In Production) loadings
    """
    queryset = (
        BeamLoading.objects
        .select_related("beam", "loom", "sizing_outcome", "created_by", "updated_by")
        .prefetch_related("productions")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BeamLoadingFilter
    search_fields = [
        "beam__beam_number",
        "loom__loom_code",
        "sizing_outcome__set_no",
        "warp_count",
        "weft_count",
    ]
    ordering_fields = [
        "id",
        "installation_date",
        "status",
        "reed_width",
        "pick",
        "shortage",
        "width",
        "created_at",
        "updated_at",
    ]
    ordering = ["-installation_date", "-id"]

    permission_map = {
        "GET": "beams.view",
        "POST": "beams.assign",
        "PUT": "beams.edit",
        "PATCH": "beams.edit",
        "DELETE": "beams.delete",
    }

    def get_serializer_class(self):
        if self.action == "batch":
            return BatchBeamLoadingSerializer
        return BeamLoadingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Load Beam Onto Loom",
            description=(
                f"Loaded Beam '{instance.beam.beam_number}' onto Loom '{instance.loom.loom_code}' "
                f"for SizingOutcome #{instance.sizing_outcome_id} (Set No: {instance.sizing_outcome.set_no})."
            ),
            module="Factory – Beam Loading",
            status="Success",
        )

        out = BeamLoadingSerializer(instance, context={"request": request})
        return Response(
            {
                "success": True,
                "message": f"Beam '{instance.beam.beam_number}' loaded successfully onto Loom '{instance.loom.loom_code}'.",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = BeamLoadingSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = BeamLoadingSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Beam Loading",
            description=f"Updated BeamLoading #{updated.id} (Beam: {updated.beam.beam_number}, Loom: {updated.loom.loom_code}).",
            module="Factory – Beam Loading",
            status="Success",
        )

        out = BeamLoadingSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": "Beam loading record updated successfully.",
            "data": out.data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        from django.db import transaction
        instance = self.get_object()

        if instance.status == BeamLoading.StatusChoices.IN_PRODUCTION:
            raise ValidationError({
                "detail": "Cannot delete a BeamLoading that is actively In Production. Finish or empty production first."
            })

        beam = instance.beam
        loom = instance.loom

        with transaction.atomic():
            instance.delete()
            # If the beam is still Loaded and has no other active loading, restore to AVAILABLE
            has_other_active = BeamLoading.objects.filter(
                beam=beam,
                status__in=[BeamLoading.StatusChoices.LOADED, BeamLoading.StatusChoices.IN_PRODUCTION]
            ).exists()
            if not has_other_active and beam.status == Beam.StatusChoices.LOADED:
                beam.status = Beam.StatusChoices.AVAILABLE
                beam.save(update_fields=["status", "updated_at"])

            # If loom is still IN_USE and has no other active loading, restore to ACTIVE
            from factory.loom.models import Loom
            has_other_loom = BeamLoading.objects.filter(
                loom=loom,
                status__in=[BeamLoading.StatusChoices.LOADED, BeamLoading.StatusChoices.IN_PRODUCTION]
            ).exists()
            if not has_other_loom and loom.status == Loom.StatusChoices.IN_USE:
                loom.status = Loom.StatusChoices.ACTIVE
                loom.save(update_fields=["status", "updated_at"])

        log_activity(
            request=request,
            action="Delete Beam Loading",
            description=f"Deleted BeamLoading #{instance.id} (Beam: {beam.beam_number}).",
            module="Factory – Beam Loading",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Beam loading record deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="batch")
    def batch(self, request):
        """
        Loads multiple Beams for a single SizingOutcome in one atomic operation.
        """
        if not request.user.is_superuser and not request.user.has_perm_code("beams.assign"):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to assign beams.")

        serializer = BatchBeamLoadingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        so_obj = serializer.validated_data["sizing_outcome_obj"]
        loadings_data = serializer.validated_data["loadings"]

        from .services import load_beam_onto_loom
        from django.db import transaction

        created_loadings = []
        with transaction.atomic():
            for item in loadings_data:
                beam_id = item.get("beam_id") or item.get("beamId") or item.get("beam")
                loom_id = item.get("loom_id") or item.get("loomId") or item.get("loom")
                inst_date = item.get("installation_date") or item.get("installationDate")

                extra = {
                    k: v for k, v in item.items()
                    if k not in ["beam_id", "beamId", "beam", "loom_id", "loomId", "loom", "installation_date", "installationDate"]
                }
                if inst_date:
                    extra["installation_date"] = inst_date

                loading = load_beam_onto_loom(
                    sizing_outcome=so_obj,
                    beam_or_id=beam_id,
                    loom_or_id=loom_id,
                    user=request.user,
                    request=request,
                    **extra
                )
                created_loadings.append(loading)

        log_activity(
            request=request,
            action="Batch Load Beams",
            description=f"Loaded {len(created_loadings)} beams onto looms for SizingOutcome #{so_obj.id}.",
            module="Factory – Beam Loading",
            status="Success",
        )

        out = BeamLoadingSerializer(created_loadings, many=True, context={"request": request})
        return Response(
            {
                "success": True,
                "message": f"Successfully loaded {len(created_loadings)} beams for Sizing Set '{so_obj.set_no}'.",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="empty")
    def empty(self, request, pk=None):
        """
        Marks the loaded Beam as physically empty:
        - Beam.status transitions to AVAILABLE (ready for reuse in subsequent sizing sets)
        - BeamLoading.status transitions to COMPLETED (history preserved)
        - Loom.status transitions back to ACTIVE
        """
        if not request.user.is_superuser and not (
            request.user.has_perm_code("beams.assign")
            or request.user.has_perm_code("looms.production")
        ):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to mark beams as empty.")

        instance = self.get_object()
        from .services import mark_beam_empty_and_available
        updated = mark_beam_empty_and_available(
            beam_loading_or_id=instance,
            user=request.user,
            request=request,
        )

        out = BeamLoadingSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": f"Beam '{updated.beam.beam_number}' has been emptied and is now AVAILABLE for new sizing sets.",
            "data": out.data,
        })

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """
        Returns all beam loadings currently Loaded or In Production.
        """
        qs = self.filter_queryset(
            self.get_queryset().filter(
                status__in=[BeamLoading.StatusChoices.LOADED, BeamLoading.StatusChoices.IN_PRODUCTION]
            )
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = BeamLoadingSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = BeamLoadingSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class ProductionViewSet(ModelViewSet):
    """
    ModelViewSet for Production operations.
    Records cloth/fabric production built from a loaded Beam on a Loom.

    Endpoints:
        GET    /productions/       – list (filterable by beam_loading, beam, loom, date, shift, beam_emptied)
        POST   /productions/       – log daily meters produced (atomically marks Beam & Loading as IN_PRODUCTION;
                                     if beam_emptied=True, marks Beam AVAILABLE)
        GET    /productions/{id}/  – retrieve
        PATCH  /productions/{id}/  – partial update
        DELETE /productions/{id}/  – delete
        GET    /productions/stats/ – aggregate metrics (total meters, entry count)
    """
    queryset = (
        Production.objects
        .select_related("beam_loading", "beam", "loom", "created_by", "updated_by")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductionFilter
    search_fields = [
        "operator_name",
        "beam__beam_number",
        "loom__loom_code",
        "remarks",
    ]
    ordering_fields = [
        "id",
        "production_date",
        "meters_produced",
        "created_at",
        "updated_at",
    ]
    ordering = ["-production_date", "-id"]

    permission_map = {
        "GET": "looms.view",
        "POST": "looms.production",
        "PUT": "looms.production",
        "PATCH": "looms.production",
        "DELETE": "looms.delete",
    }

    def get_serializer_class(self):
        return ProductionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Record Production",
            description=(
                f"Recorded {instance.meters_produced}m produced on Loom '{instance.loom.loom_code}' "
                f"from Beam '{instance.beam.beam_number}' (Shift: {instance.shift})."
            ),
            module="Factory – Production",
            status="Success",
        )

        out = ProductionSerializer(instance, context={"request": request})
        return Response(
            {
                "success": True,
                "message": f"Recorded {instance.meters_produced} meters of production successfully.",
                "data": out.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ProductionSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = ProductionSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Production Entry",
            description=f"Updated Production #{updated.id} ({updated.meters_produced}m on Loom '{updated.loom.loom_code}').",
            module="Factory – Production",
            status="Success",
        )

        out = ProductionSerializer(updated, context={"request": request})
        return Response({
            "success": True,
            "message": "Production entry updated successfully.",
            "data": out.data,
        })

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        meters = instance.meters_produced
        loom_code = instance.loom.loom_code
        instance.delete()

        log_activity(
            request=request,
            action="Delete Production Entry",
            description=f"Deleted Production #{instance.id} ({meters}m on Loom '{loom_code}').",
            module="Factory – Production",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Production record deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        Aggregate production stats: total meters produced, total entries, total beams emptied.
        """
        from django.db.models import Sum, Count
        qs = self.filter_queryset(self.get_queryset())

        agg = qs.aggregate(
            total_meters=Sum("meters_produced"),
            total_entries=Count("id"),
        )
        emptied_count = qs.filter(beam_emptied=True).count()

        return Response({
            "success": True,
            "data": {
                "totalMetersProduced": str(agg["total_meters"] or "0.00"),
                "totalEntries": agg["total_entries"],
                "totalBeamsEmptied": emptied_count,
            }
        })


