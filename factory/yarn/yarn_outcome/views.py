"""
Views for YarnOutcome – full CRUD via ModelViewSet.

All mutations (CREATE / UPDATE / DELETE) use:
  - transaction.atomic()
  - select_for_update() on YarnStock (and legacy YarnIntake if linked)
  - stock validation before write against shared YarnStock balance
  - recalculate_yarn_stock() after write
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity

from factory.yarn.yarn_stock.models import YarnStock
from factory.yarn.yarn_stock.services import (
    recalculate_yarn_stock,
    validate_outcome_stock_pool,
)
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome
from factory.yarn.yarn_intake.serializers import YarnOutcomeSerializer
from factory.yarn.yarn_intake.services import (
    recalculate_yarn_intake_stock,
)
from factory.yarn.yarn_outcome.filters import YarnOutcomeFilter


class YarnOutcomeViewSet(ModelViewSet):
    """
    CRUD for YarnOutcome with atomic shared YarnStock management.

    GET    /yarn-outcomes/
    POST   /yarn-outcomes/          → validates stock against pool, calculates weights, updates pool
    GET    /yarn-outcomes/{id}/
    PUT    /yarn-outcomes/{id}/     → validates stock excl. old outcome, recalculates stock pool
    PATCH  /yarn-outcomes/{id}/     → partial update with same safety
    DELETE /yarn-outcomes/{id}/     → removes outcome, recalculates stock pool (stock returns)
    """

    queryset = (
        YarnOutcome.objects
        .select_related(
            "stock",
            "yarn_intake",
            "yarn_intake__supplier",
            "yarn_buyer",
            "sizing",
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
        "stock__yarn_name",
        "stock__yarn_count",
        "stock__yarn_type",
        "stock__production_type",
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
        stock = validated.get("stock")
        intake = validated.get("yarn_intake")
        if not stock and intake:
            stock = intake.stock
        if not stock:
            raise ValidationError({"stock": ["A valid YarnStock pool must be selected."]})

        outcome_bags = validated["outcome_bags"]
        outcome_weight_per_bag_kg = validated["outcome_weight_per_bag_kg"]
        calc_weight_kg = Decimal(str(outcome_bags)) * Decimal(str(outcome_weight_per_bag_kg))

        try:
            with transaction.atomic():
                # Lock the stock row to prevent race conditions
                locked_stock = (
                    YarnStock.objects
                    .select_for_update()
                    .get(pk=stock.pk)
                )

                # Validate stock pool balance
                validate_outcome_stock_pool(
                    stock=locked_stock,
                    outcome_bags=outcome_bags,
                    outcome_weight_kg=calc_weight_kg,
                )

                # Build and save the outcome
                outcome = YarnOutcome(
                    stock=locked_stock,
                    yarn_intake=intake,
                    outcome_type=validated.get("outcome_type", YarnOutcome.OutcomeTypeChoices.SIZING),
                    outcome_bags=outcome_bags,
                    outcome_cones_per_bag=validated.get("outcome_cones_per_bag", 0),
                    outcome_weight_per_bag_kg=outcome_weight_per_bag_kg,
                    yarn_buyer=validated.get("yarn_buyer"),
                    sizing=validated.get("sizing"),
                    total_price=validated.get("total_price", 0),
                    outcome_date=validated["outcome_date"],
                    notes=validated.get("notes", ""),
                )

                if request.user and request.user.is_authenticated:
                    outcome.created_by = request.user
                    outcome.updated_by = request.user

                outcome.calculate_outcome_fields()
                outcome.save()

                # Recalculate shared stock pool
                recalculate_yarn_stock(locked_stock)

                # If tied to an intake, recalculate intake denormalized fields
                if intake:
                    locked_intake = YarnIntake.objects.select_for_update().get(pk=intake.pk)
                    recalculate_yarn_intake_stock(locked_intake)

                # When outcomeType is Sizing: create SizingBeamAssignment using created YarnOutcome id
                if outcome.outcome_type == YarnOutcome.OutcomeTypeChoices.SIZING:
                    from factory.yarn.sizing.models import SizingBeamAssignment
                    from factory.yarn.sizing.services import assign_beams_to_outcome

                    raw_beam_ids = (
                        request.data.get("beam_ids")
                        or request.data.get("beamIds")
                        or validated.get("beamIds")
                    )
                    single_beam = (
                        request.data.get("beam")
                        or request.data.get("beam_id")
                        or request.data.get("beamId")
                        or validated.get("beam")
                        or validated.get("beamId")
                    )

                    user = request.user if request.user and request.user.is_authenticated else None
                    if raw_beam_ids and isinstance(raw_beam_ids, list):
                        assign_beams_to_outcome(
                            outcome=outcome,
                            beam_ids=raw_beam_ids,
                            user=user,
                            request=request,
                        )
                    elif single_beam:
                        assign_beams_to_outcome(
                            outcome=outcome,
                            beam_ids=[single_beam],
                            user=user,
                            request=request,
                        )
                    else:
                        SizingBeamAssignment.objects.create(
                            yarn_outcome=outcome,
                            status=SizingBeamAssignment.StatusChoices.ASSIGNED,
                            created_by=user,
                            updated_by=user,
                        )

        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        log_activity(
            request=request,
            action="Create Yarn Outcome",
            description=(
                f"Created {outcome.outcome_type} outcome of {outcome.outcome_bags} bags "
                f"from stock pool '{locked_stock.yarn_name}' ({locked_stock.yarn_count})."
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
        new_stock = validated.get("stock", instance.stock)
        new_intake = validated.get("yarn_intake", instance.yarn_intake)
        if not new_stock and new_intake:
            new_stock = new_intake.stock

        new_outcome_bags = validated.get("outcome_bags", instance.outcome_bags)
        new_weight_per_bag_kg = validated.get(
            "outcome_weight_per_bag_kg", instance.outcome_weight_per_bag_kg
        )
        calc_weight_kg = Decimal(str(new_outcome_bags)) * Decimal(str(new_weight_per_bag_kg))

        try:
            with transaction.atomic():
                old_stock_id = instance.stock_id
                new_stock_id = new_stock.pk if new_stock else None

                # Lock stocks in order of ID to prevent deadlocks
                stock_ids = sorted(list({s for s in [old_stock_id, new_stock_id] if s is not None}))
                locked_stocks = {
                    s.pk: s
                    for s in YarnStock.objects.filter(pk__in=stock_ids).select_for_update()
                }

                locked_outcome = (
                    YarnOutcome.objects
                    .select_for_update()
                    .get(pk=instance.pk)
                )

                target_stock = locked_stocks.get(new_stock_id)
                if not target_stock:
                    raise ValidationError({"stock": ["Target stock pool does not exist."]})

                # Validate stock pool excluding this outcome if staying in same pool
                exclude_id = locked_outcome.pk if (old_stock_id == new_stock_id) else None
                validate_outcome_stock_pool(
                    stock=target_stock,
                    outcome_bags=new_outcome_bags,
                    outcome_weight_kg=calc_weight_kg,
                    exclude_outcome_id=exclude_id,
                )

                # Apply changes (skipping non-model write-only fields)
                for attr, value in validated.items():
                    if hasattr(locked_outcome, attr):
                        setattr(locked_outcome, attr, value)

                locked_outcome.stock = target_stock
                if new_intake:
                    locked_outcome.yarn_intake = new_intake

                if request.user and request.user.is_authenticated:
                    locked_outcome.updated_by = request.user

                locked_outcome.calculate_outcome_fields()
                locked_outcome.save()

                # Recalculate all affected stock pools
                for s in locked_stocks.values():
                    recalculate_yarn_stock(s)

                if new_intake:
                    locked_intake = YarnIntake.objects.select_for_update().get(pk=new_intake.pk)
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
                f"in stock pool '{target_stock.yarn_name}' ({target_stock.yarn_count})."
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
                locked_outcome = (
                    YarnOutcome.objects
                    .select_for_update()
                    .get(pk=instance.pk)
                )
                stock_id = locked_outcome.stock_id
                intake_id = locked_outcome.yarn_intake_id
                outcome_type = locked_outcome.outcome_type
                outcome_bags = locked_outcome.outcome_bags

                locked_stock = None
                if stock_id:
                    locked_stock = YarnStock.objects.select_for_update().get(pk=stock_id)

                locked_intake = None
                if intake_id:
                    locked_intake = YarnIntake.objects.select_for_update().get(pk=intake_id)

                # Release any active beam assignments back to Available
                from factory.beam.models import Beam
                from factory.yarn.sizing.models import SizingBeamAssignment
                for assignment in locked_outcome.beam_assignments.all():
                    if assignment.status in [
                        SizingBeamAssignment.StatusChoices.ASSIGNED,
                        SizingBeamAssignment.StatusChoices.IN_USE,
                    ]:
                        for b in assignment.beam.all():
                            b.status = Beam.StatusChoices.AVAILABLE
                            b.save(update_fields=["status"])
                locked_outcome.beam_assignments.all().delete()

                # Delete the outcome
                locked_outcome.delete()

                # Recalculate stock balance (automatically restored)
                if locked_stock:
                    recalculate_yarn_stock(locked_stock)
                if locked_intake:
                    recalculate_yarn_intake_stock(locked_intake)

        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        stock_name = locked_stock.yarn_name if locked_stock else "Unknown"
        log_activity(
            request=request,
            action="Delete Yarn Outcome",
            description=(
                f"Deleted {outcome_type} outcome of {outcome_bags} bags "
                f"from stock pool '{stock_name}'. Stock restored."
            ),
            module="Yarn – Outcome",
            status="Success",
        )

        return Response(
            {"success": True, "message": "Yarn outcome deleted successfully. Stock restored."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="assign-beams")
    def assign_beams(self, request, pk=None):
        """
        Assigns one or multiple Beams to this YarnOutcome (when outcome_type == 'Sizing').
        Payload:
            { "beam_ids": [101, 102] } or { "beamIds": [101, 102] } or { "beam": 101 }
        """
        from factory.yarn.sizing.services import assign_beams_to_outcome
        from factory.yarn.sizing.serializers import SizingBeamAssignmentSerializer

        outcome = self.get_object()
        if outcome.outcome_type != YarnOutcome.OutcomeTypeChoices.SIZING:
            return Response(
                {"success": False, "message": "Beams can only be assigned to Sizing outcomes."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_beam_ids = (
            request.data.get("beam_ids")
            or request.data.get("beamIds")
        )
        single_beam = (
            request.data.get("beam")
            or request.data.get("beam_id")
            or request.data.get("beamId")
        )

        beam_ids = raw_beam_ids if raw_beam_ids else ([single_beam] if single_beam else [])
        if not beam_ids:
            return Response(
                {"success": False, "message": "At least one beam ID must be provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_assignments = assign_beams_to_outcome(
            outcome=outcome,
            beam_ids=beam_ids,
            user=request.user if request.user and request.user.is_authenticated else None,
            request=request,
        )

        out_serializer = SizingBeamAssignmentSerializer(
            created_assignments, many=True, context={"request": request}
        )
        return Response(
            {
                "success": True,
                "message": f"Successfully assigned {len(beam_ids)} beam(s) to Yarn Outcome #{outcome.id}.",
                "data": {
                    "yarnOutcomeId": outcome.id,
                    "totalBeamsAssigned": outcome.total_beams,
                    "assignments": out_serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="beams")
    def beams(self, request, pk=None):
        """Lists all Beams assigned to this YarnOutcome."""
        from factory.yarn.sizing.serializers import SizingBeamAssignmentSerializer
        outcome = self.get_object()
        assignments = (
            outcome.beam_assignments
            .select_related("created_by", "updated_by")
            .prefetch_related("beam")
            .all()
        )
        serializer = SizingBeamAssignmentSerializer(assignments, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": {
                "yarnOutcomeId": outcome.id,
                "outcomeDate": outcome.outcome_date,
                "totalBeams": outcome.total_beams,
                "assignments": serializer.data,
            }
        })
