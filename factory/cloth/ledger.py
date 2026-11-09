"""
Inventory Ledger service for Cloth/Fabric Stock.

Calculates exact inventory ledger balances with incoming (inflow) and outgoing (outflow)
movements, preserving full decimal precision without lossy float conversion.
"""

from datetime import date as date_type
from decimal import Decimal
import csv
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.utils.dateparse import parse_date

from .models import ClothStock, ClothName, ClothStockMovement, CleanClothStock

ZERO = Decimal("0.000000")

ENTRY_INCOMING = "INCOMING"
ENTRY_OUTGOING = "OUTGOING"
ENTRY_TYPES = (ENTRY_INCOMING, ENTRY_OUTGOING)

MAIN_CSV_COLUMNS = [
    ("Quality / Cloth Name", "cloth_name"),
    ("Warp Count", "warp_count"),
    ("Weft Count", "weft_count"),
    ("Current Stock (Meters)", "current_stock_meters"),
    ("Current Bundles", "current_stock_bundles"),
    ("Total Incoming (Meters)", "total_incoming_meters"),
    ("Total Incoming Bundles", "total_incoming_bundles"),
    ("Total Outgoing (Meters)", "total_outgoing_meters"),
    ("Total Outgoing Bundles", "total_outgoing_bundles"),
    ("Total Movements", "total_movements_count"),
    ("Last Movement Date", "last_movement_date"),
    ("Stock Status", "status"),
]

DETAIL_CSV_COLUMNS = [
    ("Date", "date"),
    ("Type", "movement_type"),
    ("Category / Subtype", "sub_type"),
    ("Cloth Quality", "cloth_name"),
    ("Reference / DC #", "reference_number"),
    ("Party / Recipient / Source", "party_name"),
    ("Incoming (Meters)", "quantity_in"),
    ("Incoming Bundles", "bundle_in"),
    ("Outgoing (Meters)", "quantity_out"),
    ("Outgoing Bundles", "bundle_out"),
    ("Running Stock (Meters)", "running_balance"),
    ("Running Bundles", "running_bundles"),
    ("Rate / Meter (PKR)", "rate_per_meter"),
    ("Total Value (PKR)", "total_amount"),
    ("Remarks", "remarks"),
]


def _dec(value):
    """Return value as exact Decimal (None -> ZERO)."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def exact_str(value):
    """Full-precision string representation for a Decimal without scientific notation."""
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


def get_main_inventory_ledger(date_from=None, date_to=None, search=None, ordering="cloth_name"):
    """
    Computes consolidated inventory ledger rows for all ClothStock items.
    """
    stocks_qs = ClothStock.objects.select_related("cloth_name").all()

    if search:
        s = search.strip()
        stocks_qs = stocks_qs.filter(
            Q(cloth_name__name__icontains=s) |
            Q(cloth_name__warp_count__icontains=s) |
            Q(cloth_name__weft_count__icontains=s) |
            Q(cloth_name__description__icontains=s)
        )

    if ordering in ("cloth_name", "name"):
        stocks_qs = stocks_qs.order_by("cloth_name__name")
    elif ordering in ("-cloth_name", "-name"):
        stocks_qs = stocks_qs.order_by("-cloth_name__name")
    elif ordering in ("total_length", "-total_length"):
        stocks_qs = stocks_qs.order_by(ordering)
    else:
        stocks_qs = stocks_qs.order_by("cloth_name__name")

    rows = []
    tot_available = ZERO
    tot_inflow = ZERO
    tot_outflow = ZERO
    tot_in_bundles = 0
    tot_out_bundles = 0
    tot_avail_bundles = 0
    tot_transactions = 0

    for stock in stocks_qs:
        all_movs = ClothStockMovement.objects.filter(cloth_stock=stock)

        # All-time totals to calculate real current available stock
        all_time_in = all_movs.filter(movement_type=ClothStockMovement.MovementType.INCOMING).aggregate(
            q=Sum("quantity"), b=Sum("bundle_count")
        )
        all_time_out = all_movs.filter(movement_type=ClothStockMovement.MovementType.OUTGOING).aggregate(
            q=Sum("quantity"), b=Sum("bundle_count")
        )

        all_in_m = _dec(all_time_in["q"])
        all_out_m = _dec(all_time_out["q"])
        all_in_b = all_time_in["b"] or 0
        all_out_b = all_time_out["b"] or 0

        current_stock_m = max(ZERO, all_in_m - all_out_m)
        current_stock_b = max(0, all_in_b - all_out_b)

        # Period-filtered movements if date filter applied
        period_movs = all_movs
        if date_from:
            period_movs = period_movs.filter(transaction_date__gte=date_from)
        if date_to:
            period_movs = period_movs.filter(transaction_date__lte=date_to)

        period_in = period_movs.filter(movement_type=ClothStockMovement.MovementType.INCOMING).aggregate(
            q=Sum("quantity"), b=Sum("bundle_count")
        )
        period_out = period_movs.filter(movement_type=ClothStockMovement.MovementType.OUTGOING).aggregate(
            q=Sum("quantity"), b=Sum("bundle_count")
        )

        period_in_m = _dec(period_in["q"])
        period_out_m = _dec(period_out["q"])
        period_in_b = period_in["b"] or 0
        period_out_b = period_out["b"] or 0

        mov_count = period_movs.count()
        last_mov = all_movs.order_by("-transaction_date", "-id").first()
        last_date = str(last_mov.transaction_date) if last_mov else None

        # Determine stock status
        if current_stock_m > Decimal("100.000000"):
            status_label = "In Stock"
        elif current_stock_m > ZERO:
            status_label = "Low Stock"
        else:
            status_label = "Out of Stock"

        rows.append({
            "id": stock.id,
            "clothStockId": stock.id,
            "cloth_stock_id": stock.id,
            "clothNameId": stock.cloth_name.id,
            "cloth_name_id": stock.cloth_name.id,
            "clothName": stock.cloth_name.name,
            "cloth_name": stock.cloth_name.name,
            "warpCount": stock.cloth_name.warp_count or "",
            "warp_count": stock.cloth_name.warp_count or "",
            "weftCount": stock.cloth_name.weft_count or "",
            "weft_count": stock.cloth_name.weft_count or "",
            "reedCount": exact_str(stock.cloth_name.reed_count),
            "reed_count": exact_str(stock.cloth_name.reed_count),
            "pickCount": exact_str(stock.cloth_name.pick_count),
            "pick_count": exact_str(stock.cloth_name.pick_count),
            "reedWidth": exact_str(stock.cloth_name.reed_width),
            "reed_width": exact_str(stock.cloth_name.reed_width),
            "currentStock": exact_str(current_stock_m),
            "current_stock_meters": exact_str(current_stock_m),
            "currentStockRaw": current_stock_m,
            "currentBundles": current_stock_b,
            "current_stock_bundles": current_stock_b,
            "totalIncoming": exact_str(period_in_m),
            "total_incoming_meters": exact_str(period_in_m),
            "totalIncomingRaw": period_in_m,
            "totalIncomingBundles": period_in_b,
            "total_incoming_bundles": period_in_b,
            "totalOutgoing": exact_str(period_out_m),
            "total_outgoing_meters": exact_str(period_out_m),
            "totalOutgoingRaw": period_out_m,
            "totalOutgoingBundles": period_out_b,
            "total_outgoing_bundles": period_out_b,
            "totalMovements": mov_count,
            "total_movements_count": mov_count,
            "lastMovementDate": last_date,
            "last_movement_date": last_date,
            "status": status_label,
        })

        tot_available += current_stock_m
        tot_avail_bundles += current_stock_b
        tot_inflow += period_in_m
        tot_in_bundles += period_in_b
        tot_outflow += period_out_m
        tot_out_bundles += period_out_b
        tot_transactions += mov_count

    active_qualities = sum(1 for r in rows if r["currentStockRaw"] > ZERO)

    summary = {
        "totalAvailableStock": exact_str(tot_available),
        "total_available_stock_meters": exact_str(tot_available),
        "totalAvailableBundles": tot_avail_bundles,
        "total_available_bundles": tot_avail_bundles,
        "totalIncoming": exact_str(tot_inflow),
        "total_incoming_meters": exact_str(tot_inflow),
        "totalIncomingBundles": tot_in_bundles,
        "total_incoming_bundles": tot_in_bundles,
        "totalOutgoing": exact_str(tot_outflow),
        "total_outgoing_meters": exact_str(tot_outflow),
        "totalOutgoingBundles": tot_out_bundles,
        "total_outgoing_bundles": tot_out_bundles,
        "totalQualitiesCount": len(rows),
        "total_qualities_count": len(rows),
        "activeQualitiesCount": active_qualities,
        "active_qualities_count": active_qualities,
        "totalTransactionsCount": tot_transactions,
        "total_transactions_count": tot_transactions,
    }

    return {
        "rows": rows,
        "summary": summary,
    }


def build_individual_inventory_ledger(
    cloth_stock_id,
    date_from=None,
    date_to=None,
    movement_type=None,
    search=None,
    ordering="-date",
):
    """
    Computes exact chronological running balance ledger for an individual ClothStock.
    """
    stock = ClothStock.objects.select_related("cloth_name").get(id=cloth_stock_id)

    # 1. Calculate opening balance prior to date_from
    opening_balance = ZERO
    opening_bundles = 0

    if date_from:
        prior_movs = ClothStockMovement.objects.filter(
            cloth_stock=stock,
            transaction_date__lt=date_from
        )
        prior_in = prior_movs.filter(movement_type=ClothStockMovement.MovementType.INCOMING).aggregate(
            q=Sum("quantity"), b=Sum("bundle_count")
        )
        prior_out = prior_movs.filter(movement_type=ClothStockMovement.MovementType.OUTGOING).aggregate(
            q=Sum("quantity"), b=Sum("bundle_count")
        )
        p_in_q = _dec(prior_in["q"])
        p_out_q = _dec(prior_out["q"])
        p_in_b = prior_in["b"] or 0
        p_out_b = prior_out["b"] or 0
        opening_balance = max(ZERO, p_in_q - p_out_q)
        opening_bundles = max(0, p_in_b - p_out_b)

    # 2. Query movements within the window (ordered chronologically for running balance)
    movs_qs = ClothStockMovement.objects.filter(cloth_stock=stock)

    if date_from:
        movs_qs = movs_qs.filter(transaction_date__gte=date_from)
    if date_to:
        movs_qs = movs_qs.filter(transaction_date__lte=date_to)

    if movement_type:
        movs_qs = movs_qs.filter(movement_type=movement_type)

    if search:
        s = search.strip()
        movs_qs = movs_qs.filter(
            Q(reference_number__icontains=s) |
            Q(party_name__icontains=s) |
            Q(sub_type__icontains=s) |
            Q(remarks__icontains=s)
        )

    chronological_movs = list(movs_qs.order_by("transaction_date", "id"))

    # 3. Accumulate running balance
    running_m = opening_balance
    running_b = opening_bundles

    period_in_m = ZERO
    period_out_m = ZERO
    period_in_b = 0
    period_out_b = 0

    rows = []
    for mov in chronological_movs:
        is_in = mov.movement_type == ClothStockMovement.MovementType.INCOMING
        qty = mov.quantity
        bundles = mov.bundle_count or 1

        if is_in:
            running_m += qty
            running_b += bundles
            period_in_m += qty
            period_in_b += bundles
            qty_in_str = exact_str(qty)
            qty_out_str = None
            bundle_in = bundles
            bundle_out = None
        else:
            running_m = max(ZERO, running_m - qty)
            running_b = max(0, running_b - bundles)
            period_out_m += qty
            period_out_b += bundles
            qty_in_str = None
            qty_out_str = exact_str(qty)
            bundle_in = None
            bundle_out = bundles

        rows.append({
            "id": mov.id,
            "movementId": mov.id,
            "date": str(mov.transaction_date),
            "movementType": mov.movement_type,
            "movement_type": mov.movement_type,
            "subType": mov.sub_type,
            "sub_type": mov.sub_type,
            "reference": mov.reference_number,
            "reference_number": mov.reference_number,
            "partyName": mov.party_name,
            "party_name": mov.party_name,
            "quantityIn": qty_in_str,
            "quantity_in": qty_in_str,
            "quantityOut": qty_out_str,
            "quantity_out": qty_out_str,
            "bundleIn": bundle_in,
            "bundle_in": bundle_in,
            "bundleOut": bundle_out,
            "bundle_out": bundle_out,
            "runningBalance": exact_str(running_m),
            "running_balance": exact_str(running_m),
            "runningBundles": running_b,
            "running_bundles": running_b,
            "ratePerMeter": exact_str(mov.rate_per_meter),
            "rate_per_meter": exact_str(mov.rate_per_meter),
            "totalAmount": exact_str(mov.total_amount),
            "total_amount": exact_str(mov.total_amount),
            "remarks": mov.remarks,
            "isProduction": bool(mov.clean_cloth_stock_id),
            "is_production": bool(mov.clean_cloth_stock_id),
            "cleanClothStockId": mov.clean_cloth_stock_id,
            "createdAt": mov.created_at.isoformat() if mov.created_at else None,
        })

    # Display ordering: reverse if descending by date
    if ordering in ("-date", "-transaction_date"):
        display_rows = list(reversed(rows))
    else:
        display_rows = rows

    summary = {
        "openingBalance": exact_str(opening_balance),
        "opening_balance": exact_str(opening_balance),
        "openingBundles": opening_bundles,
        "opening_bundles": opening_bundles,
        "closingBalance": exact_str(running_m),
        "closing_balance": exact_str(running_m),
        "closingBundles": running_b,
        "closing_bundles": running_b,
        "periodIncoming": exact_str(period_in_m),
        "period_incoming": exact_str(period_in_m),
        "periodOutgoing": exact_str(period_out_m),
        "period_outgoing": exact_str(period_out_m),
        "netChange": exact_str(period_in_m - period_out_m),
        "net_change": exact_str(period_in_m - period_out_m),
        "periodIncomingBundles": period_in_b,
        "period_incoming_bundles": period_in_b,
        "periodOutgoingBundles": period_out_b,
        "period_outgoing_bundles": period_out_b,
        "totalMovements": len(rows),
        "total_movements": len(rows),
    }

    cloth_data = {
        "id": stock.id,
        "clothStockId": stock.id,
        "cloth_stock_id": stock.id,
        "clothName": stock.cloth_name.name,
        "cloth_name": stock.cloth_name.name,
        "warpCount": stock.cloth_name.warp_count or "",
        "weftCount": stock.cloth_name.weft_count or "",
        "reedCount": exact_str(stock.cloth_name.reed_count),
        "pickCount": exact_str(stock.cloth_name.pick_count),
        "reedWidth": exact_str(stock.cloth_name.reed_width),
        "currentStock": exact_str(stock.total_length),
    }

    return {
        "cloth": cloth_data,
        "summary": summary,
        "rows": display_rows,
    }


def export_inventory_ledger_csv(cloth_stock_id=None, date_from=None, date_to=None):
    """
    Renders CSV export for inventory ledger.
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8")

    if cloth_stock_id:
        res = build_individual_inventory_ledger(
            cloth_stock_id=cloth_stock_id,
            date_from=date_from,
            date_to=date_to,
            ordering="date"
        )
        cloth_name_sanitized = res["cloth"]["clothName"].replace(" ", "_").lower()
        response["Content-Disposition"] = f'attachment; filename="inventory_ledger_{cloth_name_sanitized}.csv"'

        writer = csv.writer(response)
        writer.writerow([f"Inventory Ledger — {res['cloth']['clothName']}"])
        writer.writerow([f"Opening Balance: {res['summary']['openingBalance']} m ({res['summary']['openingBundles']} bundles)"])
        writer.writerow([f"Closing Balance: {res['summary']['closingBalance']} m ({res['summary']['closingBundles']} bundles)"])
        writer.writerow([])

        writer.writerow([col[0] for col in DETAIL_CSV_COLUMNS])
        for row in res["rows"]:
            row_data = dict(row)
            row_data["cloth_name"] = res["cloth"]["clothName"]
            writer.writerow([row_data.get(col[1], "") or "" for col in DETAIL_CSV_COLUMNS])
    else:
        res = get_main_inventory_ledger(date_from=date_from, date_to=date_to)
        response["Content-Disposition"] = 'attachment; filename="inventory_stock_ledger_summary.csv"'

        writer = csv.writer(response)
        writer.writerow(["Inventory Stock Ledger — Master Summary"])
        writer.writerow([f"Total Available Stock: {res['summary']['totalAvailableStock']} m"])
        writer.writerow([])

        writer.writerow([col[0] for col in MAIN_CSV_COLUMNS])
        for row in res["rows"]:
            writer.writerow([row.get(col[1], "") or "" for col in MAIN_CSV_COLUMNS])

    return response

