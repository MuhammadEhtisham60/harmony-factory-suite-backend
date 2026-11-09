"""
Customer Cloth Ledger API Views.

Endpoints:
    GET  /api/v1/customer-ledger/             -> Main Customer Cloth Ledger (all customers with balances & aggregates)
    GET  /api/v1/customer-ledger/{id}/        -> Individual Customer Statement (transactions, running balances, opening balance)
    GET  /api/v1/customer-ledger/transactions/ -> Flat chronological transactions stream
    POST /api/v1/customer-ledger/payments/    -> Record a payment received from customer (with bank sync)
    POST /api/v1/customer-ledger/sales/       -> Record a cloth sale / invoice
    GET  /api/v1/customer-ledger/export/      -> CSV export (main overview or individual customer statement)
    GET  /api/v1/customer-ledger/choices/     -> Choice lists (payment methods, statuses)

    ClothSaleViewSet (/api/v1/cloth-sales/):  -> Full CRUD on ClothSale models
"""

import csv
from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet, ModelViewSet

from accounts.pagination import StandardResultsSetPagination
from accounts.permissions import HasERPModulePermission
from audit_logs.utils import log_activity
from factory.sales.customer.models import Customer
from .models import ClothSale, ClothCustomerPayment
from .ledger import (
    CSV_COLUMNS,
    MAIN_CSV_COLUMNS,
    ENTRY_TYPES,
    ZERO,
    build_customer_cloth_ledger,
    csv_value,
    exact_str,
    get_main_customer_cloth_ledger,
)
from .serializers import (
    ClothSaleSerializer,
    ClothCustomerPaymentSerializer,
    CustomerLedgerRowSerializer,
    CustomerLedgerBalanceSerializer,
    IndividualCustomerLedgerSummarySerializer,
    MainCustomerLedgerItemSerializer,
    MainCustomerLedgerSummarySerializer,
)


class CustomerClothLedgerViewSet(ViewSet):
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    required_permission = ["customers.view", "sale.view"]

    @staticmethod
    def _parse_date(params, key):
        raw = params.get(key)
        if not raw:
            return None
        parsed = parse_date(raw)
        if parsed is None:
            raise ValidationError({key: "Enter a valid date in YYYY-MM-DD format."})
        return parsed

    def _parse_filters(self, request):
        params = request.query_params
        errors = {}

        customer_id = params.get("customer") or params.get("customer_id")
        if customer_id not in (None, ""):
            try:
                customer_id = int(customer_id)
            except (TypeError, ValueError):
                errors["customer"] = "Customer ID must be an integer."
        else:
            customer_id = None

        entry_type = params.get("entry_type") or None
        if entry_type is not None and entry_type not in ENTRY_TYPES:
            errors["entry_type"] = f"Must be one of: {', '.join(ENTRY_TYPES)}."

        ordering = params.get("ordering") or "customer_name"
        allowed_orderings = (
            "customer_name", "-customer_name",
            "customer_code", "-customer_code",
            "company_name", "-company_name",
            "total_meters_sold", "-total_meters_sold",
            "total_sales", "-total_sales",
            "total_paid", "-total_paid",
            "total_receivables", "-total_receivables",
            "date", "-date"
        )
        if ordering not in allowed_orderings:
            ordering = "customer_name"

        try:
            date_from = self._parse_date(params, "date_from")
        except ValidationError as exc:
            errors.update(exc.detail)
            date_from = None
        try:
            date_to = self._parse_date(params, "date_to")
        except ValidationError as exc:
            errors.update(exc.detail)
            date_to = None

        if not errors and date_from and date_to and date_from > date_to:
            errors["date_from"] = "date_from cannot be after date_to."

        if errors:
            raise ValidationError(errors)

        return {
            "customer_id": customer_id,
            "date_from": date_from,
            "date_to": date_to,
            "entry_type": entry_type,
            "ordering": ordering,
            "search": params.get("search", "").strip() or None,
            "status": params.get("status", "").strip() or None,
            "customer_type": params.get("customer_type", "").strip() or None,
        }

    def list(self, request):
        """
        Main Customer Cloth Ledger overview:
        Returns all customers with aggregated cloth meters, total sales,
        total paid, net balance receivables, plus overall summary KPI cards.
        """
        filters = self._parse_filters(request)
        ledger_result = get_main_customer_cloth_ledger(
            search=filters["search"],
            status=filters["status"],
            customer_type=filters["customer_type"],
            ordering=filters["ordering"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
        )

        items = ledger_result["items"]
        summary = ledger_result["summary"]

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(items, request)
        serializer = MainCustomerLedgerItemSerializer(page, many=True)
        summary_serializer = MainCustomerLedgerSummarySerializer(summary)

        total_pages = (
            (paginator.page.paginator.num_pages)
            if hasattr(paginator, "page") and paginator.page
            else 1
        )

        return Response({
            "count": len(items),
            "totalPages": total_pages,
            "summary": summary_serializer.data,
            "results": serializer.data,
        })

    def retrieve(self, request, pk=None):
        """
        Individual Customer Statement Ledger:
        Returns opening balance, full chronological transactions stream with
        running balances, and summary metrics.
        """
        customer = get_object_or_404(Customer, pk=pk)
        filters = self._parse_filters(request)

        ledger_data = build_customer_cloth_ledger(
            customer=customer,
            date_from=filters["date_from"],
            date_to=filters["date_to"],
            entry_type=filters["entry_type"],
            ordering=filters["ordering"] if filters["ordering"] in ("date", "-date") else "date",
        )

        row_serializer = CustomerLedgerRowSerializer(ledger_data["rows"], many=True)
        opening_serializer = CustomerLedgerBalanceSerializer(ledger_data["openingBalance"])
        summary_serializer = IndividualCustomerLedgerSummarySerializer(ledger_data["summary"])

        return Response({
            "customer": ledger_data["customer"],
            "openingBalance": opening_serializer.data,
            "summary": summary_serializer.data,
            "rows": row_serializer.data,
        })

    @action(detail=False, methods=["GET"])
    def transactions(self, request):
        """
        Chronological transactions across all or a single customer.
        """
        filters = self._parse_filters(request)
        customer_id = filters["customer_id"]

        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)
            ledger_data = build_customer_cloth_ledger(
                customer=customer,
                date_from=filters["date_from"],
                date_to=filters["date_to"],
                entry_type=filters["entry_type"],
                ordering=filters["ordering"] if filters["ordering"] in ("date", "-date") else "date",
            )
            rows = ledger_data["rows"]
        else:
            # Build across all customers
            customers = Customer.objects.all()
            rows = []
            for c in customers:
                ld = build_customer_cloth_ledger(
                    customer=c,
                    date_from=filters["date_from"],
                    date_to=filters["date_to"],
                    entry_type=filters["entry_type"],
                    ordering="date",
                )
                if ld:
                    rows.extend(ld["rows"])
            reverse = filters["ordering"] == "-date"
            rows.sort(key=lambda r: (r["date"], r["_rank"], r["_created_at"] or r["date"], r["_pk"] or 0), reverse=reverse)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(rows, request)
        serializer = CustomerLedgerRowSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=["GET", "POST"])
    def payments(self, request):
        """
        GET: List recorded customer payments.
        POST: Record a new payment from a customer.
        """
        if request.method == "POST":
            serializer = ClothCustomerPaymentSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            payment = serializer.save(created_by=request.user)

            c_name = payment.customer.customer_name if payment.customer else "Customer"
            log_activity(
                request=request,
                action="Record Customer Payment",
                description=f"Received payment of Rs. {payment.amount} from Customer {c_name} via {payment.payment_method}",
                module="Sales – Customer Ledger",
                status="Success",
                user=request.user,
            )

            return Response({
                "message": "Customer payment recorded successfully.",
                "data": ClothCustomerPaymentSerializer(payment).data,
            }, status=status.HTTP_201_CREATED)

        # GET: list payments
        qs = ClothCustomerPayment.objects.all().select_related("customer", "bank_account", "cloth_sale")
        cust_id = request.query_params.get("customer") or request.query_params.get("customer_id")
        if cust_id:
            qs = qs.filter(customer_id=cust_id)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        ser = ClothCustomerPaymentSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["GET", "POST"])
    def sales(self, request):
        """
        GET: List cloth sales.
        POST: Record a new cloth sale / invoice.
        """
        if request.method == "POST":
            serializer = ClothSaleSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            sale = serializer.save(created_by=request.user, updated_by=request.user)

            # If deduct_from_stock requested, atomically decrement ClothStock
            if sale.deduct_from_stock and sale.cloth_name_id:
                try:
                    from factory.cloth.models import ClothStock
                    stock = ClothStock.objects.filter(cloth_name_id=sale.cloth_name_id).first()
                    if stock and stock.total_length >= sale.quantity_meters:
                        stock.total_length -= Decimal(str(sale.quantity_meters))
                        stock.save(update_fields=["total_length", "updated_at"])
                except Exception:
                    pass

            c_name = sale.customer.customer_name if sale.customer else "Customer"
            cloth = sale.cloth_name.name if sale.cloth_name else "Cloth"
            log_activity(
                request=request,
                action="Create Cloth Sale",
                description=f"Recorded sale {sale.invoice_number} of {sale.quantity_meters}m {cloth} to {c_name} (Rs. {sale.total_amount})",
                module="Sales – Customer Ledger",
                status="Success",
                user=request.user,
            )

            return Response({
                "message": "Cloth sale recorded successfully.",
                "data": ClothSaleSerializer(sale).data,
            }, status=status.HTTP_201_CREATED)

        qs = ClothSale.objects.all().select_related("customer", "cloth_name")
        cust_id = request.query_params.get("customer") or request.query_params.get("customer_id")
        if cust_id:
            qs = qs.filter(customer_id=cust_id)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        ser = ClothSaleSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["GET"])
    def choices(self, request):
        """
        Dropdown values for customer ledger UI.
        """
        return Response({
            "paymentMethods": [
                {"value": k, "label": v} for k, v in ClothCustomerPayment.PaymentMethod.choices
            ],
            "saleStatuses": [
                {"value": k, "label": v} for k, v in ClothSale.StatusChoices.choices
            ],
            "paymentStatuses": [
                {"value": k, "label": v} for k, v in ClothSale.PaymentStatusChoices.choices
            ],
            "customerTypes": [
                {"value": k, "label": v} for k, v in Customer.CustomerType.choices
            ],
        })

    @action(detail=False, methods=["GET"])
    def export(self, request):
        """
        CSV Export:
        - If customer or customer_id is provided, exports Individual Customer Statement.
        - Otherwise, exports Main Customer Ledger summary.
        """
        filters = self._parse_filters(request)
        customer_id = filters["customer_id"]

        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)
            ledger_data = build_customer_cloth_ledger(
                customer=customer,
                date_from=filters["date_from"],
                date_to=filters["date_to"],
                entry_type=filters["entry_type"],
                ordering=filters["ordering"] if filters["ordering"] in ("date", "-date") else "date",
            )
            response = HttpResponse(content_type="text/csv")
            filename = f"customer-statement-{customer.customer_code}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow([label for label, _ in CSV_COLUMNS])

            # Opening balance row
            op = ledger_data["openingBalance"]
            writer.writerow([
                csv_value(op.get("date") or "Opening"),
                "Opening Balance",
                customer.customer_code,
                customer.customer_name,
                "B/F Balance",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                csv_value(op["balance_meters"]),
                csv_value(op["balance_receivables"]),
                "Brought Forward Opening Balance",
            ])

            for row in ledger_data["rows"]:
                writer.writerow([csv_value(row.get(fld)) for _, fld in CSV_COLUMNS])

            return response
        else:
            ledger_result = get_main_customer_cloth_ledger(
                search=filters["search"],
                status=filters["status"],
                customer_type=filters["customer_type"],
                ordering=filters["ordering"],
                date_from=filters["date_from"],
                date_to=filters["date_to"],
            )
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="customer-cloth-ledger-summary.csv"'

            writer = csv.writer(response)
            writer.writerow([label for label, _ in MAIN_CSV_COLUMNS])
            for item in ledger_result["items"]:
                writer.writerow([csv_value(item.get(fld)) for _, fld in MAIN_CSV_COLUMNS])

            return response


class ClothSaleViewSet(ModelViewSet):
    """
    Standard ModelViewSet for Cloth Sale / Invoices.
    """
    permission_classes = [IsAuthenticated, HasERPModulePermission]
    required_permission = ["sale.view", "customers.view"]
    pagination_class = StandardResultsSetPagination
    serializer_class = ClothSaleSerializer

    def get_queryset(self):
        qs = ClothSale.objects.all().select_related("customer", "cloth_name")
        c_id = self.request.query_params.get("customer") or self.request.query_params.get("customer_id")
        if c_id:
            qs = qs.filter(customer_id=c_id)
        status_val = self.request.query_params.get("status")
        if status_val:
            qs = qs.filter(status=status_val)
        pay_status = self.request.query_params.get("payment_status")
        if pay_status:
            qs = qs.filter(payment_status=pay_status)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(invoice_number__icontains=search)
                | models.Q(customer__customer_name__icontains=search)
                | models.Q(cloth_name__name__icontains=search)
                | models.Q(delivery_challan_no__icontains=search)
            )
        return qs.order_by("-sale_date", "-id")

    def perform_create(self, serializer):
        sale = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        if sale.deduct_from_stock and sale.cloth_name_id:
            try:
                from factory.cloth.models import ClothStock
                stock = ClothStock.objects.filter(cloth_name_id=sale.cloth_name_id).first()
                if stock and stock.total_length >= sale.quantity_meters:
                    stock.total_length -= Decimal(str(sale.quantity_meters))
                    stock.save(update_fields=["total_length", "updated_at"])
            except Exception:
                pass
        log_activity(
            request=self.request,
            action="Create Cloth Sale",
            description=f"Created Cloth Sale {sale.invoice_number} ({sale.quantity_meters}m to {sale.customer.customer_name})",
            module="Sales",
            status="Success",
            user=self.request.user,
        )

    def perform_destroy(self, instance):
        inv_no = instance.invoice_number
        super().perform_destroy(instance)
        log_activity(
            request=self.request,
            action="Delete Cloth Sale",
            description=f"Deleted Cloth Sale {inv_no}",
            module="Sales",
            status="Success",
            user=self.request.user,
        )
