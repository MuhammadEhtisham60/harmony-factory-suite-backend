"""
Views for YarnIntake – full CRUD via ModelViewSet.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from .models import YarnIntake
from .serializers import YarnIntakeListSerializer, YarnIntakeDetailSerializer
from .filters import YarnIntakeFilter


class YarnIntakeViewSet(ModelViewSet):
    """
    CRUD for YarnIntake.

    GET  /yarn-intakes/        → paginated list (no nested outcomes)
    GET  /yarn-intakes/{id}/   → full detail WITH nested outcomes[]
    POST /yarn-intakes/        → create, backend calculates all derived fields
    PUT  /yarn-intakes/{id}/   → full update
    PATCH /yarn-intakes/{id}/  → partial update
    DELETE /yarn-intakes/{id}/ → destroy (cascades YarnOutcomes)
    """

    queryset = (
        YarnIntake.objects
        .select_related("supplier", "created_by", "updated_by")
        .prefetch_related("outcomes", "outcomes__yarn_buyer")
        .all()
    )
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnIntakeFilter
    search_fields = [
        "yarn_name", "yarn_type", "yarn_count", "set_no",
        "production_type", "supplier__supplier_name",
    ]
    ordering_fields = [
        "yarn_name", "yarn_type", "yarn_count", "set_no",
        "intake_date", "bags", "remaining_bags", "created_at", "updated_at",
    ]
    ordering = ["-intake_date", "-id"]

    permission_map = {
        "GET": "yarn_intake.view",
        "POST": "yarn_intake.add",
        "PUT": "yarn_intake.edit",
        "PATCH": "yarn_intake.edit",
        "DELETE": "yarn_intake.delete",
    }

    def get_serializer_class(self):
        if self.action == "list":
            return YarnIntakeListSerializer
        return YarnIntakeDetailSerializer

    def _get_fresh_instance(self, pk):
        """Fetch intake with prefetch for serialization after write."""
        return (
            YarnIntake.objects
            .select_related("supplier", "created_by", "updated_by")
            .prefetch_related("outcomes", "outcomes__yarn_buyer")
            .get(pk=pk)
        )

    def create(self, request, *args, **kwargs):
        serializer = YarnIntakeDetailSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Yarn Intake",
            description=(
                f"Created yarn intake '{instance.yarn_name}' "
                f"Set: {instance.set_no}, {instance.bags} bags."
            ),
            module="Yarn – Intake",
            status="Success",
        )

        out = YarnIntakeDetailSerializer(
            self._get_fresh_instance(instance.pk), context={"request": request}
        )
        return Response(
            {"success": True, "message": "Yarn intake created successfully.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = YarnIntakeDetailSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = YarnIntakeDetailSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Yarn Intake",
            description=(
                f"Updated yarn intake '{updated.yarn_name}' "
                f"Set: {updated.set_no}."
            ),
            module="Yarn – Intake",
            status="Success",
        )

        out = YarnIntakeDetailSerializer(
            self._get_fresh_instance(updated.pk), context={"request": request}
        )
        return Response(
            {"success": True, "message": "Yarn intake updated successfully.", "data": out.data}
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.yarn_name
        set_no = instance.set_no
        instance.delete()

        log_activity(
            request=request,
            action="Delete Yarn Intake",
            description=f"Deleted yarn intake '{name}' Set: {set_no}.",
            module="Yarn – Intake",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn intake deleted successfully."},
            status=status.HTTP_200_OK,
        )
