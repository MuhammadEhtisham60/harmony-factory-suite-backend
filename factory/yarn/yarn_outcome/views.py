"""
Views for YarnOutcome – full CRUD via ModelViewSet.

All mutations (CREATE / UPDATE / DELETE) use:
  - transaction.atomic()
  - select_for_update() on the parent YarnIntake
  - stock validation before write
  - recalculate_yarn_intake_stock() after write
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError

from django.db import transaction

from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome
from factory.yarn.yarn_intake.serializers import YarnOutcomeSerializer
from factory.yarn.yarn_intake.services import (
    recalculate_yarn_intake_stock,
    validate_outcome_stock,
)
from factory.yarn.yarn_outcome.filters import YarnOutcomeFilter


class YarnOutcomeViewSet(ModelViewSet):
    """
    CRUD for YarnOutcome with atomic stock management.

    GET    /yarn-outcomes/
    POST   /yarn-outcomes/          → validates stock, calculates weights, updates intake summary
    GET    /yarn-outcomes/{id}/
    PUT    /yarn-outcomes/{id}/     → validates stock excl. old outcome, recalculates intake
    PATCH  /yarn-outcomes/{id}/     → partial update with same safety
    DELETE /yarn-outcomes/{id}/     → removes outcome, recalculates intake (stock returns)
    """

    queryset = (
        YarnOutcome.objects
        .select_related(
            "yarn_intake",
            "yarn_intake__supplier",
            "yarn_buyer",
            "created_by",
            "updated_by",
        )
        .all()
    )
    serializer_class = YarnOutcomeSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnOutcomeFilter
    search_fields = [
        "yarn_intake__yarn_name",
        "yarn_intake__set_no",
        "outcome_type",
        "yarn_buyer__buyer_name",
    ]
    ordering_fields = [
        "outcome_date", "outcome_type", "outcome_bags",
        "outcome_weight_kg", "total_price", "created_at",
    ]
    ordering = ["-outcome_date", "-id"]

    permission_map = {
        "GET": "yarn_outcome.view",
        "POST": "yarn_outcome.add",
        "PUT": "yarn_outcome.edit",
        "PATCH": "yarn_outcome.edit",
        "DELETE": "yarn_outcome.delete",
    }

    # ──────────────────────────────────────────────────────────────────────
    # CREATE
    # ──────────────────────────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        serializer = YarnOutcomeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        intake = validated["yarn_intake"]
        outcome_bags = validated["outcome_bags"]

        try:
            with transaction.atomic():
                # Lock the intake row to prevent race conditions
                locked_intake = (
                    YarnIntake.objects
                    .select_for_update()
                    .get(pk=intake.pk)
                )

                # Validate stock
                try:
                    validate_outcome_stock(locked_intake, outcome_bags)
                except ValueError as e:
                    raise ValidationError(e.args[0])

                # Build and save the outcome
                outcome = YarnOutcome(
                    yarn_intake=locked_intake,
                    outcome_type=validated.get("outcome_type", YarnOutcome.OutcomeTypeChoices.SIZING),
                    outcome_bags=outcome_bags,
                    outcome_cones_per_bag=validated.get("outcome_cones_per_bag", 0),
                    outcome_weight_per_bag_kg=validated["outcome_weight_per_bag_kg"],
                    yarn_buyer=validated.get("yarn_buyer"),
                    total_price=validated.get("total_price", 0),
                    outcome_date=validated["outcome_date"],
                    notes=validated.get("notes", ""),
                )

                if request.user and request.user.is_authenticated:
                    outcome.created_by = request.user
                    outcome.updated_by = request.user

                outcome.calculate_outcome_fields()
                outcome.save()

                # Recalculate intake summary from actual outcomes
                recalculate_yarn_intake_stock(locked_intake)

        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        log_activity(
            request=request,
            action="Create Yarn Outcome",
            description=(
                f"Created {outcome.outcome_type} outcome of {outcome.outcome_bags} bags "
                f"from intake '{locked_intake.yarn_name}' (Set: {locked_intake.set_no})."
            ),
            module="Yarn – Outcome",
            status="Success",
        )

        out = YarnOutcomeSerializer(outcome, context={"request": request})
        return Response(
            {"success": True, "message": "Yarn outcome created successfully.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    # ──────────────────────────────────────────────────────────────────────
    # RETRIEVE
    # ──────────────────────────────────────────────────────────────────────

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = YarnOutcomeSerializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    # ──────────────────────────────────────────────────────────────────────
    # UPDATE (PUT / PATCH)
    # ──────────────────────────────────────────────────────────────────────

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = YarnOutcomeSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        new_intake = validated.get("yarn_intake", instance.yarn_intake)
        new_outcome_bags = validated.get("outcome_bags", instance.outcome_bags)

        try:
            with transaction.atomic():
                # Lock both the current intake and the (possibly new) intake
                locked_intake = (
                    YarnIntake.objects
                    .select_for_update()
                    .get(pk=new_intake.pk)
                )

                # Also lock the existing outcome
                locked_outcome = (
                    YarnOutcome.objects
                    .select_for_update()
                    .get(pk=instance.pk)
                )

                # Validate stock EXCLUDING this outcome's current bags
                # (so we properly account for the old value being replaced)
                try:
                    validate_outcome_stock(
                        locked_intake,
                        new_outcome_bags,
                        exclude_outcome_id=locked_outcome.pk
                    )
                except ValueError as e:
                    raise ValidationError(e.args[0])

                # Apply changes
                for attr, value in validated.items():
                    setattr(locked_outcome, attr, value)

                if request.user and request.user.is_authenticated:
                    locked_outcome.updated_by = request.user

                locked_outcome.calculate_outcome_fields()
                locked_outcome.save()

                # Recalculate intake summary
                recalculate_yarn_intake_stock(locked_intake)

        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        log_activity(
            request=request,
            action="Update Yarn Outcome",
            description=(
                f"Updated {locked_outcome.outcome_type} outcome to {locked_outcome.outcome_bags} bags "
                f"from intake '{locked_intake.yarn_name}' (Set: {locked_intake.set_no})."
            ),
            module="Yarn – Outcome",
            status="Success",
        )

        out = YarnOutcomeSerializer(locked_outcome, context={"request": request})
        return Response(
            {"success": True, "message": "Yarn outcome updated successfully.", "data": out.data}
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # ──────────────────────────────────────────────────────────────────────
    # DELETE
    # ──────────────────────────────────────────────────────────────────────

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            with transaction.atomic():
                # Lock the parent intake
                locked_intake = (
                    YarnIntake.objects
                    .select_for_update()
                    .get(pk=instance.yarn_intake_id)
                )

                outcome_type = instance.outcome_type
                outcome_bags = instance.outcome_bags
                intake_name = locked_intake.yarn_name
                intake_set = locked_intake.set_no

                # Delete the outcome
                instance.delete()

                # Recalculate from remaining outcomes (stock automatically restored)
                recalculate_yarn_intake_stock(locked_intake)

        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        log_activity(
            request=request,
            action="Delete Yarn Outcome",
            description=(
                f"Deleted {outcome_type} outcome of {outcome_bags} bags "
                f"from intake '{intake_name}' (Set: {intake_set}). Stock restored."
            ),
            module="Yarn – Outcome",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Yarn outcome deleted successfully. Stock restored."},
            status=status.HTTP_200_OK,
        )
