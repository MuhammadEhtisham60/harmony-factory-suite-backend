"""
Views for Sizing – full CRUD via ModelViewSet.
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

from .models import Sizing
from .serializers import SizingSerializer
from .filters import SizingFilter


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
        GET    /sizings/choices/    → dropdown list for YarnOutcome form
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
