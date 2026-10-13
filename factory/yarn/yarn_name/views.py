"""
Views for YarnName – full CRUD via ModelViewSet.
"""

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

from .models import YarnName
from .serializers import YarnNameSerializer
from .filters import YarnNameFilter


class YarnNameViewSet(ModelViewSet):
    """
    CRUD ModelViewSet for YarnName.
    Endpoints:
        GET    /api/v1/yarn-names/         – list (filterable, paginated)
        POST   /api/v1/yarn-names/         – create
        GET    /api/v1/yarn-names/{id}/    – retrieve
        PUT    /api/v1/yarn-names/{id}/    – full update
        PATCH  /api/v1/yarn-names/{id}/    – partial update
        DELETE /api/v1/yarn-names/{id}/    – delete
        GET    /api/v1/yarn-names/choices/ – dropdown choices
    """
    queryset = YarnName.objects.select_related("created_by", "updated_by").all()
    serializer_class = YarnNameSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnNameFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "status", "created_at", "updated_at"]
    ordering = ["name"]

    permission_map = {
        "GET": "yarn_intake.view",
        "POST": "yarn_intake.add",
        "PUT": "yarn_intake.edit",
        "PATCH": "yarn_intake.edit",
        "DELETE": "yarn_intake.delete",
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Yarn Name",
            description=f"Created yarn name '{instance.name}'.",
            module="Yarn – Setup",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn name created successfully.", "data": serializer.data},
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
            action="Update Yarn Name",
            description=f"Updated yarn name '{updated.name}'.",
            module="Yarn – Setup",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn name updated successfully.", "data": serializer.data}
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name
        instance.delete()

        log_activity(
            request=request,
            action="Delete Yarn Name",
            description=f"Deleted yarn name '{name}'.",
            module="Yarn – Setup",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn name deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """Returns compact list of active yarn names for dropdowns."""
        qs = self.get_queryset().filter(status=YarnName.StatusChoices.ACTIVE)
        data = [{"id": item.id, "name": item.name} for item in qs]
        return Response({"success": True, "data": data})
