"""
Customer Cloth Ledger computation engine.

Builds read-only financial and material ledger views for Customers who purchase woven cloth:
  1. SALE (Cloth dispatched / sold to customer) -> ClothSale
  2. PAYMENT (Payment received from customer)   -> ClothCustomerPayment

Running balances (receivables) are accumulated per customer in exact Decimal
with NO float conversion, NO silent rounding, and large context precision (60 digits).
"""

from datetime import date as date_type
from decimal import Decimal, localcontext

from django.db.models import Sum, Count, Q
from django.utils.dateparse import parse_date

from factory.sales.customer.models import Customer
from .models import ClothSale, ClothCustomerPayment

ZERO = Decimal("0")
LEDGER_DECIMAL_PRECISION = 60

ENTRY_SALE = "sale"
ENTRY_PAYMENT = "payment"
ENTRY_TYPES = (ENTRY_SALE, ENTRY_PAYMENT)

CSV_COLUMNS = [
    ("Date", "date"),
    ("Type", "entry_type"),
    ("Customer Code", "customer_code"),
    ("Customer Name", "customer_name"),
    ("Reference", "reference"),
    ("Invoice Number", "invoice_number"),
    ("Cloth Quality", "cloth_quality"),
    ("Meters Sold", "quantity_meters"),
    ("Rate / Meter", "rate_per_meter"),
    ("Sale Amount (Debit)", "sale_amount"),
    ("Payment Method", "payment_method"),
    ("Payment Amount (Credit)", "payment_amount"),
    ("Amount Paid", "amount_paid"),
    ("Amount Due", "amount_due"),
    ("Payment Status", "payment_status"),
    ("Delivery Challan", "delivery_challan_no"),
    ("Balance Meters", "balance_meters"),
    ("Balance Receivables", "balance_receivables"),
    ("Remarks", "remarks"),
]

MAIN_CSV_COLUMNS = [
    ("Customer Code", "customer_code"),
    ("Customer Name", "customer_name"),
    ("Company Name", "company_name"),
    ("Contact Person", "contact_person"),
    ("Phone", "phone"),
    ("Email", "email"),
    ("Customer Type", "customer_type"),
    ("Status", "status"),
    ("Total Meters Sold", "total_meters_sold"),
    ("Total Sales", "total_sales"),
    ("Total Received", "total_paid"),
    ("Net Receivables", "total_receivables"),
    ("Invoices Count", "sales_count"),
    ("Payments Count", "payments_count"),
    ("Transactions Count", "transactions_count"),
]


def _dec(value):
    """Return value as an exact Decimal (None -> ZERO). Never converts to float."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def exact_str(value):
    """Full-precision plain-notation string for a Decimal (no scientific exponent)."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        s = format(value, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
            if not s:
                s = "0"
        return s
    return str(value)


def csv_value(val):
    if val is None:
        return ""
    if isinstance(val, Decimal):
        return exact_str(val)
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (date_type,)):
        return val.isoformat()
    return str(val).strip()


def _blank_row():
    return {
        "id": "",
        "entry_type": "",
        "date": None,
        "_rank": 0,
        "_created_at": None,
        "_pk": None,
        "customer_id": None,
        "customer_code": "",
        "customer_name": "",
        "reference": "",
        "cloth_sale_id": None,
        "payment_id": None,
        "invoice_number": "",
        "cloth_name_id": None,
        "cloth_quality": "",
        "quantity_meters": ZERO,
        "rate_per_meter": ZERO,
        "sale_amount": ZERO,
        "payment_method": "",
        "reference_number": "",
        "bank_account_id": None,
        "bank_account_name": "",
        "payment_amount": ZERO,
        "amount_paid": ZERO,
        "amount_due": ZERO,
        "payment_status": "",
        "delivery_challan_no": "",
        "vehicle_no": "",
        "driver_name": "",
        "balance_meters": ZERO,
        "cumulative_sales": ZERO,
        "cumulative_paid": ZERO,
        "balance_receivables": ZERO,
        "remarks": "",
    }


def _sale_row(cs):
    row = _blank_row()
    meters = _dec(cs.quantity_meters)
    rate = _dec(cs.rate_per_meter)
    tot = _dec(cs.total_amount) or (meters * rate)
    amt_paid = _dec(cs.amount_paid)
    amt_due = _dec(cs.amount_due) if cs.amount_due is not None else max(ZERO, tot - amt_paid)
    cloth_title = cs.cloth_name.name if cs.cloth_name else "Woven Cloth"

    row.update({
        "id": f"SALE-{cs.id}",
        "entry_type": ENTRY_SALE,
        "date": cs.sale_date,
        "_rank": 0,
        "_created_at": cs.created_at,
        "_pk": cs.id,
        "customer_id": cs.customer_id,
        "customer_code": cs.customer.customer_code if cs.customer else "",
        "customer_name": cs.customer.customer_name if cs.customer else "",
        "reference": cs.invoice_number or f"Sale #{cs.id}",
        "cloth_sale_id": cs.id,
        "invoice_number": cs.invoice_number or f"INV-C-{cs.id}",
        "cloth_name_id": cs.cloth_name_id,
        "cloth_quality": cloth_title,
        "quantity_meters": meters,
        "rate_per_meter": rate,
        "sale_amount": tot,
        "amount_paid": amt_paid,
        "amount_due": amt_due,
        "payment_status": cs.payment_status or "Pending",
        "delivery_challan_no": cs.delivery_challan_no or "",
        "vehicle_no": cs.vehicle_no or "",
        "driver_name": cs.driver_name or "",
        "remarks": cs.notes or f"Dispatched {meters}m of {cloth_title} (Invoice {cs.invoice_number})",
    })
    return row


def _payment_row(cp):
    row = _blank_row()
    amt = _dec(cp.amount)
    ref = cp.payment_number or f"Payment #{cp.id}"
    b_name = cp.bank_account.bank_name if cp.bank_account else ""

    row.update({
        "id": f"PAY-{cp.id}",
        "entry_type": ENTRY_PAYMENT,
        "date": cp.payment_date,
        "_rank": 1,
        "_created_at": cp.created_at,
        "_pk": cp.id,
        "customer_id": cp.customer_id,
        "customer_code": cp.customer.customer_code if cp.customer else "",
        "customer_name": cp.customer.customer_name if cp.customer else "",
        "reference": ref,
        "payment_id": cp.id,
        "cloth_sale_id": cp.cloth_sale_id,
        "invoice_number": cp.cloth_sale.invoice_number if cp.cloth_sale else "",
        "payment_method": cp.payment_method,
        "reference_number": cp.reference_number or "",
        "bank_account_id": cp.bank_account_id,
        "bank_account_name": b_name,
        "payment_amount": amt,
        "remarks": cp.notes or f"Received via {cp.payment_method}{f' ({b_name})' if b_name else ''}",
    })
    return row


def build_customer_cloth_ledger(customer, date_from=None, date_to=None, entry_type=None, ordering="date"):
    """
    Computes an exact chronological ledger statement for an individual Customer.
    Running balance starts from opening balance (before date_from) and updates:
      - SALE adds to balance_receivables (debit - customer owes us)
      - PAYMENT subtracts from balance_receivables (credit - customer paid us)
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        cust_id = customer.id if hasattr(customer, "id") else customer
        cust_obj = Customer.objects.filter(id=cust_id).first() if not hasattr(customer, "customer_name") else customer
        if not cust_obj:
            return None

        # 1. Opening Balance Calculation (prior to date_from)
        opening_meters = ZERO
        opening_sales = ZERO
        opening_paid = ZERO
        opening_receivables = ZERO

        if date_from:
            sales_prior = ClothSale.objects.filter(customer_id=cust_id, sale_date__lt=date_from)
            sales_prior_aggr = sales_prior.aggregate(
                meters=Sum("quantity_meters"),
                total=Sum("total_amount")
            )
            opening_meters = _dec(sales_prior_aggr["meters"])
            opening_sales = _dec(sales_prior_aggr["total"])

            payments_prior = ClothCustomerPayment.objects.filter(customer_id=cust_id, payment_date__lt=date_from)
            payments_prior_aggr = payments_prior.aggregate(
                total=Sum("amount")
            )
            opening_paid = _dec(payments_prior_aggr["total"])
            opening_receivables = opening_sales - opening_paid

        # 2. Fetch rows in the active date range
        sales_qs = ClothSale.objects.filter(customer_id=cust_id).select_related("cloth_name", "customer")
        payments_qs = ClothCustomerPayment.objects.filter(customer_id=cust_id).select_related("bank_account", "customer", "cloth_sale")

        if date_from:
            sales_qs = sales_qs.filter(sale_date__gte=date_from)
            payments_qs = payments_qs.filter(payment_date__gte=date_from)
        if date_to:
            sales_qs = sales_qs.filter(sale_date__lte=date_to)
            payments_qs = payments_qs.filter(payment_date__lte=date_to)

        rows = []
        if entry_type in (None, "", ENTRY_SALE):
            for cs in sales_qs:
                rows.append(_sale_row(cs))
        if entry_type in (None, "", ENTRY_PAYMENT):
            for cp in payments_qs:
                rows.append(_payment_row(cp))

        # Sort chronologically: date asc, rank asc (sales first on same date), created_at asc, id asc
        rows.sort(key=lambda r: (r["date"], r["_rank"], r["_created_at"] or r["date"], r["_pk"] or 0))

        # 3. Accumulate running balances
        curr_meters = opening_meters
        curr_sales = opening_sales
        curr_paid = opening_paid
        curr_receivables = opening_receivables

        period_meters_sold = ZERO
        period_sales = ZERO
        period_paid = ZERO

        for r in rows:
            if r["entry_type"] == ENTRY_SALE:
                curr_meters += r["quantity_meters"]
                curr_sales += r["sale_amount"]
                curr_receivables += r["sale_amount"]
                period_meters_sold += r["quantity_meters"]
                period_sales += r["sale_amount"]
            elif r["entry_type"] == ENTRY_PAYMENT:
                curr_paid += r["payment_amount"]
                curr_receivables -= r["payment_amount"]
                period_paid += r["payment_amount"]

            r["balance_meters"] = curr_meters
            r["cumulative_sales"] = curr_sales
            r["cumulative_paid"] = curr_paid
            r["balance_receivables"] = curr_receivables

        # Apply display ordering (default "date", or "-date" descending)
        if ordering == "-date":
            rows.reverse()

        opening_balance = {
            "date": date_from,
            "balanceMeters": opening_meters,
            "cumulativeSales": opening_sales,
            "cumulativePaid": opening_paid,
            "balanceReceivables": opening_receivables,
            "balance_meters": opening_meters,
            "cumulative_sales": opening_sales,
            "cumulative_paid": opening_paid,
            "balance_receivables": opening_receivables,
        }

        summary = {
            "totalMetersSold": period_meters_sold,
            "totalSales": period_sales,
            "totalPaid": period_paid,
            "totalReceivables": curr_receivables,
            "total_meters_sold": period_meters_sold,
            "total_sales": period_sales,
            "total_paid": period_paid,
            "total_receivables": curr_receivables,
            "salesCount": len([r for r in rows if r["entry_type"] == ENTRY_SALE]),
            "paymentsCount": len([r for r in rows if r["entry_type"] == ENTRY_PAYMENT]),
            "transactionsCount": len(rows),
            "sales_count": len([r for r in rows if r["entry_type"] == ENTRY_SALE]),
            "payments_count": len([r for r in rows if r["entry_type"] == ENTRY_PAYMENT]),
            "transactions_count": len(rows),
        }

        customer_details = {
            "id": cust_obj.id,
            "customerCode": cust_obj.customer_code,
            "customerName": cust_obj.customer_name,
            "companyName": cust_obj.company_name or "",
            "contactPerson": cust_obj.contact_person or "",
            "phone": cust_obj.phone or "",
            "email": cust_obj.email or "",
            "address": cust_obj.address or "",
            "customerType": cust_obj.customer_type,
            "status": cust_obj.status,
            "customer_code": cust_obj.customer_code,
            "customer_name": cust_obj.customer_name,
            "company_name": cust_obj.company_name or "",
            "contact_person": cust_obj.contact_person or "",
            "customer_type": cust_obj.customer_type,
        }

        return {
            "customer": customer_details,
            "openingBalance": opening_balance,
            "summary": summary,
            "rows": rows,
        }


def get_main_customer_cloth_ledger(search=None, status=None, customer_type=None, ordering="customer_name", date_from=None, date_to=None):
    """
    Computes summary metrics for all customers with filter, search, and aggregate totals.
    """
    with localcontext() as ctx:
        ctx.prec = LEDGER_DECIMAL_PRECISION

        qs = Customer.objects.all()

        if status:
            qs = qs.filter(status=status)
        if customer_type:
            qs = qs.filter(customer_type=customer_type)
        if search:
            s = search.strip()
            qs = qs.filter(
                Q(customer_name__icontains=s)
                | Q(customer_code__icontains=s)
                | Q(company_name__icontains=s)
                | Q(phone__icontains=s)
                | Q(contact_person__icontains=s)
            )

        customers = list(qs)
        cust_ids = [c.id for c in customers]

        # Aggregate sales per customer
        sales_qs = ClothSale.objects.filter(customer_id__in=cust_ids)
        if date_from:
            sales_qs = sales_qs.filter(sale_date__gte=date_from)
        if date_to:
            sales_qs = sales_qs.filter(sale_date__lte=date_to)

        sales_data = {}
        for row in sales_qs.values("customer_id").annotate(
            tot_meters=Sum("quantity_meters"),
            tot_sales=Sum("total_amount"),
            cnt=Count("id")
        ):
            sales_data[row["customer_id"]] = {
                "meters": _dec(row["tot_meters"]),
                "sales": _dec(row["tot_sales"]),
                "count": row["cnt"],
            }

        # Aggregate payments per customer
        payments_qs = ClothCustomerPayment.objects.filter(customer_id__in=cust_ids)
        if date_from:
            payments_qs = payments_qs.filter(payment_date__gte=date_from)
        if date_to:
            payments_qs = payments_qs.filter(payment_date__lte=date_to)

        payments_data = {}
        for row in payments_qs.values("customer_id").annotate(
            tot_paid=Sum("amount"),
            cnt=Count("id")
        ):
            payments_data[row["customer_id"]] = {
                "paid": _dec(row["tot_paid"]),
                "count": row["cnt"],
            }

        items = []
        overall_meters = ZERO
        overall_sales = ZERO
        overall_paid = ZERO
        overall_receivables = ZERO

        for c in customers:
            sd = sales_data.get(c.id, {"meters": ZERO, "sales": ZERO, "count": 0})
            pd = payments_data.get(c.id, {"paid": ZERO, "count": 0})

            tot_m = sd["meters"]
            tot_s = sd["sales"]
            tot_p = pd["paid"]
            net_bal = tot_s - tot_p

            overall_meters += tot_m
            overall_sales += tot_s
            overall_paid += tot_p
            overall_receivables += net_bal

            items.append({
                "id": c.id,
                "customerId": c.id,
                "customer_id": c.id,
                "customerCode": c.customer_code,
                "customer_code": c.customer_code,
                "customerName": c.customer_name,
                "customer_name": c.customer_name,
                "companyName": c.company_name or "",
                "company_name": c.company_name or "",
                "contactPerson": c.contact_person or "",
                "contact_person": c.contact_person or "",
                "phone": c.phone or "",
                "email": c.email or "",
                "address": c.address or "",
                "customerType": c.customer_type,
                "customer_type": c.customer_type,
                "status": c.status,
                "totalMetersSold": tot_m,
                "total_meters_sold": tot_m,
                "totalSales": tot_s,
                "total_sales": tot_s,
                "totalPaid": tot_p,
                "total_paid": tot_p,
                "totalReceivables": net_bal,
                "total_receivables": net_bal,
                "salesCount": sd["count"],
                "sales_count": sd["count"],
                "paymentsCount": pd["count"],
                "payments_count": pd["count"],
                "transactionsCount": sd["count"] + pd["count"],
                "transactions_count": sd["count"] + pd["count"],
            })

        # Apply sorting
        reverse_sort = ordering.startswith("-")
        sort_field = ordering.lstrip("-")

        field_map = {
            "customer_name": "customer_name",
            "customer_code": "customer_code",
            "company_name": "company_name",
            "total_meters_sold": "total_meters_sold",
            "total_sales": "total_sales",
            "total_paid": "total_paid",
            "total_receivables": "total_receivables",
        }
        key_fn = lambda x: (x.get(field_map.get(sort_field, "customer_name")) or "")
        items.sort(key=key_fn, reverse=reverse_sort)

        summary = {
            "totalCustomers": len(customers),
            "activeCustomers": len([c for c in customers if c.status == "Active"]),
            "totalMetersSold": overall_meters,
            "totalSales": overall_sales,
            "totalPaid": overall_paid,
            "totalReceivables": overall_receivables,
            "total_customers": len(customers),
            "active_customers": len([c for c in customers if c.status == "Active"]),
            "total_meters_sold": overall_meters,
            "total_sales": overall_sales,
            "total_paid": overall_paid,
            "total_receivables": overall_receivables,
        }

        return {
            "summary": summary,
            "items": items,
        }
