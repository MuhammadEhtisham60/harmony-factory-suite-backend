"""
Views for YarnBuyer – full CRUD via ModelViewSet.
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

from .models import YarnBuyer
from .serializers import YarnBuyerSerializer
from .filters import YarnBuyerFilter


class YarnBuyerViewSet(ModelViewSet):
    """
    CRUD for YarnBuyer.

    Endpoints:
        GET    /yarn-buyers/
        POST   /yarn-buyers/
        GET    /yarn-buyers/{id}/
        PUT    /yarn-buyers/{id}/
        PATCH  /yarn-buyers/{id}/
        DELETE /yarn-buyers/{id}/
        GET    /yarn-buyers/choices/
    """

    queryset = (
        YarnBuyer.objects
        .select_related("created_by", "updated_by")
        .all()
    )
    serializer_class = YarnBuyerSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnBuyerFilter
    search_fields = ["buyer_name", "company_name", "phone_no", "email", "city", "country"]
    ordering_fields = ["buyer_name", "company_name", "city", "country", "status", "created_at"]
    ordering = ["buyer_name"]

    permission_map = {
        "GET": "yarn_buyer.view",
        "POST": "yarn_buyer.add",
        "PUT": "yarn_buyer.edit",
        "PATCH": "yarn_buyer.edit",
        "DELETE": "yarn_buyer.delete",
    }

    def create(self, request, *args, **kwargs):
        serializer = YarnBuyerSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        log_activity(
            request=request,
            action="Create Yarn Buyer",
            description=f"Created yarn buyer '{instance.buyer_name}'.",
            module="Yarn – Buyers",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn buyer created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = YarnBuyerSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = YarnBuyerSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request=request,
            action="Update Yarn Buyer",
            description=f"Updated yarn buyer '{updated.buyer_name}'.",
            module="Yarn – Buyers",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn buyer updated successfully.", "data": serializer.data}
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.buyer_name
        instance.delete()

        log_activity(
            request=request,
            action="Delete Yarn Buyer",
            description=f"Deleted yarn buyer '{name}'.",
            module="Yarn – Buyers",
            status="Success",
        )
        return Response(
            {"success": True, "message": "Yarn buyer deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="choices")
    def choices(self, request):
        """Returns all yarn buyers as a minimal list for dropdowns."""
        buyers = YarnBuyer.objects.filter(status="Active").values("id", "buyer_name", "company_name")
        return Response({
            "success": True,
            "data": [
                {"value": b["id"], "label": b["buyer_name"], "company": b["company_name"]}
                for b in buyers
            ]
        })
