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
from factory.yarn.yarn_stock.serializers import YarnStockMinSerializer
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
            "stock__yarn_name",
            "stock__yarn_count",
            "stock__yarn_type",
            "yarn_buyer",
            "sizing",
            "warping",
            "created_by",
            "updated_by",
        )
        .prefetch_related(
            "items",
            "items__yarn_intake",
            "items__yarn_intake__supplier",
        )
        .all()
    )
    serializer_class = YarnOutcomeSerializer
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = YarnOutcomeFilter
    search_fields = [
        "stock__yarn_name__name",
        "stock__yarn_count__name",
        "stock__yarn_type__name",
        "stock__production_type",
        "items__yarn_intake__yarn_name__name",
        "items__yarn_intake__set_no",
        "outcome_type",
        "yarn_buyer__buyer_name",
        "warping__warping_name",
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
        # Support bulk list payload: e.g. [{"yarn_intake": 1, ...}, ...]
        if isinstance(request.data, list):
            created_outcomes = []
            with transaction.atomic():
                for item_payload in request.data:
                    serializer = YarnOutcomeSerializer(
                        data=item_payload, context={"request": request}
                    )
                    serializer.is_valid(raise_exception=True)
                    outcome = serializer.save()

                    if outcome.outcome_type in (YarnOutcome.OutcomeTypeChoices.SIZING, YarnOutcome.OutcomeTypeChoices.WARPING):
                        from factory.yarn.sizing.services import mark_beams_as_sizing
                        raw_beam_ids = item_payload.get("beam_ids") or item_payload.get("beamIds")
                        single_beam = item_payload.get("beam") or item_payload.get("beam_id") or item_payload.get("beamId")
                        user = request.user if request.user and request.user.is_authenticated else None
                        # Dispatch only marks beams as 'Sizing'; they are linked to a
                        # sizing outcome later, when the set is returned.
                        if raw_beam_ids and isinstance(raw_beam_ids, list):
                            mark_beams_as_sizing(outcome, raw_beam_ids, user=user, request=request)
                        elif single_beam:
                            mark_beams_as_sizing(outcome, [single_beam], user=user, request=request)
                    created_outcomes.append(outcome)

            log_activity(
                request=request,
                action="Create Yarn Outcomes (Bulk)",
                description=f"Created {len(created_outcomes)} yarn outcomes.",
                module="Yarn – Outcome",
                status="Success",
            )
            return Response(
                {
                    "success": True,
                    "message": f"{len(created_outcomes)} yarn outcomes created successfully.",
                    "data": [YarnOutcomeSerializer(o, context={"request": request}).data for o in created_outcomes],
                },
                status=status.HTTP_201_CREATED,
            )

        serializer = YarnOutcomeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        outcome = serializer.save()

        # When outcomeType is Sizing or Warping: mark the chosen beams appropriately.
        # They get linked to a sizing outcome later, when the set is returned.
        if outcome.outcome_type in (YarnOutcome.OutcomeTypeChoices.SIZING, YarnOutcome.OutcomeTypeChoices.WARPING):
            from factory.yarn.sizing.services import mark_beams_as_sizing

            raw_beam_ids = (
                request.data.get("beam_ids")
                or request.data.get("beamIds")
            )
            single_beam = (
                request.data.get("beam")
                or request.data.get("beam_id")
                or request.data.get("beamId")
            )

            user = request.user if request.user and request.user.is_authenticated else None
            if raw_beam_ids and isinstance(raw_beam_ids, list):
                mark_beams_as_sizing(outcome, raw_beam_ids, user=user, request=request)
            elif single_beam:
                mark_beams_as_sizing(outcome, [single_beam], user=user, request=request)

        stock_name = outcome.stock.yarn_name.name if outcome.stock and outcome.stock.yarn_name else ""
        log_activity(
            request=request,
            action="Create Yarn Outcome",
            description=(
                f"Created {outcome.outcome_type} outcome of {outcome.outcome_bags} bags "
                f"from stock pool '{stock_name}'."
            ),
            module="Yarn – Outcome",
            status="Success",
        )

        outcome.refresh_from_db()
        out = YarnOutcomeSerializer(outcome, context={"request": request})
        return Response(
            {
                "success": True,
                "message": "Yarn outcome created successfully.",
                "data": out.data,
                "stock": YarnStockMinSerializer(outcome.stock).data if outcome.stock else None,
            },
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
        outcome = serializer.save()

        stock_name = outcome.stock.yarn_name.name if outcome.stock and outcome.stock.yarn_name else ""
        log_activity(
            request=request,
            action="Update Yarn Outcome",
            description=(
                f"Updated {outcome.outcome_type} outcome to {outcome.outcome_bags} bags "
                f"in stock pool '{stock_name}'."
            ),
            module="Yarn – Outcome",
            status="Success",
        )

        outcome.refresh_from_db()
        out = YarnOutcomeSerializer(outcome, context={"request": request})
        return Response(
            {
                "success": True,
                "message": "Yarn outcome updated successfully.",
                "data": out.data,
                "stock": YarnStockMinSerializer(outcome.stock).data if outcome.stock else None,
            }
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
                outcome_type = locked_outcome.outcome_type
                outcome_bags = locked_outcome.outcome_bags

                # Collect all contributing intake IDs from items
                intake_ids = set(locked_outcome.items.values_list("yarn_intake_id", flat=True))

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

                # Delete the outcome (cascades to items and b_grade_items, handles restoration in models.delete)
                locked_outcome.delete()

                # Recalculate all affected intakes
                for i_id in sorted(list(intake_ids)):
                    locked_intake = YarnIntake.objects.select_for_update().get(pk=i_id)
                    recalculate_yarn_intake_stock(locked_intake)

                # Recalculate stock balance (automatically restored)
                locked_stock = None
                if stock_id:
                    locked_stock = YarnStock.objects.select_for_update().get(pk=stock_id)
                    recalculate_yarn_stock(locked_stock)

        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        stock_name = locked_stock.yarn_name.name if locked_stock and locked_stock.yarn_name else "Unknown"
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

        if locked_stock:
            locked_stock.refresh_from_db()
        return Response(
            {
                "success": True,
                "message": "Yarn outcome deleted successfully. Stock restored.",
                "stock": YarnStockMinSerializer(locked_stock).data if locked_stock else None,
            },
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
