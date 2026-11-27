"""
Views for YarnType – full CRUD via ModelViewSet.
"""

from django.db.models.deletion import ProtectedError
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

from .models import YarnType
from .serializers import YarnTypeSerializer
from .filters import YarnTypeFilter


class YarnTypeViewSet(ModelViewSet):
    """
    CRUD ModelViewSet for YarnType.
    Endpoints:
        GET    /api/v1/yarn-types/         – list (filterable, paginated)
        POST   /api/v1/yarn-types/         – create
        GET    /api/v1/yarn-types/{id}/    – retrieve
        PUT    /api/v1/yarn-types/{id}/    – full update
        PATCH  /api/v1/yarn-types/{id}/    – partial update
        DELETE /api/v1/yarn-types/{id}/    – delete
        GET    /api/v1/yarn-types/choices/ – dropdown choices
    """
    queryset = YarnType.objects.select_related("created_by", "updated_by").exclude(status="Deleted")
    serializer_class = YarnTypeSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnTypeFilter
    search_fields = ["name", "description"]
    ordering_fields = ["status", "created_at", "updated_at"]
    ordering = ["-created_at"]

    permission_map = {
        "GET": "yarn_intake.view",
        "POST": "yarn_intake.add",
        "PUT": "yarn_intake.edit",
        "PATCH": "yarn_intake.edit",
        "DELETE": "yarn_intake.delete",
    }

    def create(self, request, *args, **kwargs):
        raw_name = (request.data.get("name") or "").strip()
        if raw_name:
            existing_deleted = YarnType.objects.filter(name__iexact=raw_name, status="Deleted").first()
            if existing_deleted:
                existing_deleted.name = raw_name
                existing_deleted.description = request.data.get("description", existing_deleted.description or "")
                existing_deleted.status = request.data.get("status") or YarnType.StatusChoices.ACTIVE
                if request.user and request.user.is_authenticated:
                    existing_deleted.updated_by = request.user
                existing_deleted.save()
                serializer = self.get_serializer(existing_deleted)
                return Response(
                    {"success": True, "message": "Yarn type created successfully.", "data": serializer.data},
                    status=status.HTTP_201_CREATED,
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Yarn Type",
            description=f"Created yarn type '{instance.name}'.",
            module="Yarn – Setup",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn type created successfully.", "data": serializer.data},
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
            action="Update Yarn Type",
            description=f"Updated yarn type '{updated.name}'.",
            module="Yarn – Setup",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn type updated successfully.", "data": serializer.data}
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name

        if instance.status != "Inactive":
            return Response(
                {
                    "success": False,
                    "message": (
                        f"Only Inactive yarn types can be deleted. "
                        f"'{name}' is currently '{instance.status}'. "
                        f"Please mark it as Inactive first."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instance.delete()
        except ProtectedError:
            try:
                instance.yarn_stocks.all().delete()
                instance.delete()
            except ProtectedError:
                instance.status = "Deleted"
                instance.save(update_fields=["status", "updated_at"])

        log_activity(
            request=request,
            action="Delete Yarn Type",
            description=f"Deleted yarn type '{name}'.",
            module="Yarn – Setup",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn type deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """Returns compact list of active yarn types for dropdowns."""
        qs = self.get_queryset().filter(status=YarnType.StatusChoices.ACTIVE)
        data = [{"id": item.id, "name": item.name} for item in qs]
        return Response({"success": True, "data": data})
