"""
Business-logic services for the Inventory module.

All stock mutations and payment updates go through these functions to ensure
atomicity, correct ledger creation, running-balance maintenance, and payment sync.
"""

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone


def get_last_running_balance(inventory_item_id):
    """Return the most recent running_balance for the given item, or 0."""
    from factory.inventory.ledger.models import InventoryLedger

    last = (
        InventoryLedger.objects
        .filter(inventory_item_id=inventory_item_id)
        .order_by("-transaction_date", "-id")
        .first()
    )
    return last.running_balance if last else Decimal("0")


def create_opening_stock_ledger(item, created_by):
    """
    Call after creating an InventoryItem when opening_stock > 0.
    Creates the first ledger entry and syncs current_stock.
    """
    from factory.inventory.ledger.models import InventoryLedger

    if item.opening_stock and item.opening_stock > 0:
        unit_price = Decimal(str(item.purchase_price or 0)).quantize(Decimal("0.01"))
        total_amount = (Decimal(str(item.opening_stock)) * unit_price).quantize(Decimal("0.01"))
        InventoryLedger.objects.create(
            inventory_item=item,
            transaction_date=(
                item.created_at.date()
                if hasattr(item.created_at, "date")
                else item.created_at
            ),
            transaction_number=f"OPEN-{item.item_code}",
            transaction_type="Opening Stock",
            quantity_in=item.opening_stock,
            quantity_out=Decimal("0"),
            running_balance=item.opening_stock,
            unit_price=unit_price,
            total_amount=total_amount,
            amount_paid=Decimal("0.00"),
            amount_due=total_amount,
            payment_status="Pending",
            reference_type="opening",
            supplier=item.preferred_supplier,
            notes=f"Opening stock for {item.item_name}",
            created_by=created_by,
        )
        item.current_stock = item.opening_stock
        item.save(update_fields=["current_stock"])


@transaction.atomic
def confirm_purchase(purchase, confirmed_by):
    """
    Confirm an InventoryPurchase: update stock and create ledger entries
    for every line item. Raises ValidationError if already confirmed.
    """
    from factory.inventory.item.models import InventoryItem
    from factory.inventory.ledger.models import InventoryLedger

    if purchase.status == "Confirmed":
        raise ValidationError("Purchase already confirmed.")

    purchase.recompute_payment_fields()
    purchase_total = Decimal(str(purchase.total_amount or 0))
    purchase_paid = Decimal(str(purchase.amount_paid or 0))
    remaining_paid_to_allocate = purchase_paid

    line_items = list(purchase.items.select_related("inventory_item").all())
    for idx, item_line in enumerate(line_items):
        inv_item = InventoryItem.objects.select_for_update().get(
            pk=item_line.inventory_item_id
        )
        prev_balance = get_last_running_balance(inv_item.id)
        new_balance = prev_balance + item_line.quantity

        line_total = Decimal(str(item_line.total_price or 0)).quantize(Decimal("0.01"))
        if purchase_total > Decimal("0") and purchase_paid > Decimal("0"):
            if idx == len(line_items) - 1:
                line_paid = min(line_total, max(Decimal("0.00"), remaining_paid_to_allocate))
            else:
                line_paid = min(
                    line_total,
                    ((line_total / purchase_total) * purchase_paid).quantize(Decimal("0.01")),
                )
            remaining_paid_to_allocate -= line_paid
        elif purchase.payment_status == "Paid":
            line_paid = line_total
        else:
            line_paid = Decimal("0.00")

        line_due = max(Decimal("0.00"), line_total - line_paid)
        if purchase.payment_status == "Paid" or (line_total > Decimal("0") and line_paid >= line_total):
            line_status = "Paid"
        elif line_paid > Decimal("0") or purchase.payment_status == "Partially Paid":
            line_status = "Partially Paid"
        else:
            line_status = "Pending"

        InventoryLedger.objects.create(
            inventory_item=inv_item,
            transaction_date=purchase.purchase_date,
            transaction_number=f"{purchase.purchase_number}-{item_line.id}",
            transaction_type="Stock In",
            quantity_in=item_line.quantity,
            quantity_out=Decimal("0"),
            running_balance=new_balance,
            unit_price=item_line.unit_price,
            total_amount=line_total,
            amount_paid=line_paid,
            amount_due=line_due,
            payment_status=line_status,
            reference_id=purchase.id,
            reference_type="purchase",
            supplier=purchase.supplier,
            notes=(
                f"Purchase {purchase.purchase_number}"
                + (f" - {purchase.reference_number}" if purchase.reference_number else "")
            ),
            created_by=confirmed_by,
        )
        inv_item.current_stock = new_balance
        inv_item.save(update_fields=["current_stock"])

    purchase.status = "Confirmed"
    purchase.save(
        update_fields=["status", "amount_paid", "amount_due", "payment_status", "updated_at"]
    )


@transaction.atomic
def process_transaction(inv_transaction, created_by):
    """
    Process a stock-out or adjustment transaction.
    Updates current_stock and creates the ledger entry.
    Raises ValidationError for insufficient stock on deductions.
    """
    from factory.inventory.item.models import InventoryItem
    from factory.inventory.ledger.models import InventoryLedger

    inv_item = InventoryItem.objects.select_for_update().get(
        pk=inv_transaction.inventory_item_id
    )
    prev_balance = get_last_running_balance(inv_item.id)

    if inv_transaction.transaction_type in ("Stock Out", "Adjustment Out"):
        if inv_item.current_stock < inv_transaction.quantity:
            raise ValidationError(
                f"Insufficient stock. Current stock: {inv_item.current_stock}, "
                f"Requested: {inv_transaction.quantity}"
            )
        new_balance = prev_balance - inv_transaction.quantity
        qty_in, qty_out = Decimal("0"), inv_transaction.quantity
    else:  # Adjustment In
        new_balance = prev_balance + inv_transaction.quantity
        qty_in, qty_out = inv_transaction.quantity, Decimal("0")

    unit_price = Decimal(str(inv_item.purchase_price or 0)).quantize(Decimal("0.01"))
    total_amount = (Decimal(str(inv_transaction.quantity or 0)) * unit_price).quantize(
        Decimal("0.01")
    )

    InventoryLedger.objects.create(
        inventory_item=inv_item,
        transaction_date=inv_transaction.transaction_date,
        transaction_number=inv_transaction.transaction_number,
        transaction_type=inv_transaction.transaction_type,
        quantity_in=qty_in,
        quantity_out=qty_out,
        running_balance=new_balance,
        unit_price=unit_price,
        total_amount=total_amount,
        amount_paid=Decimal("0.00"),
        amount_due=total_amount,
        payment_status="Pending",
        reference_id=inv_transaction.id,
        reference_type="transaction",
        supplier=inv_item.preferred_supplier,
        notes=inv_transaction.notes,
        created_by=created_by,
    )
    inv_item.current_stock = new_balance
    inv_item.save(update_fields=["current_stock"])


def _sync_purchase_from_ledger_entries(purchase_id):
    """Recalculate parent InventoryPurchase payment status from its ledger entries."""
    from factory.inventory.purchase.models import InventoryPurchase
    from factory.inventory.ledger.models import InventoryLedger

    if not purchase_id:
        return
    purchase = InventoryPurchase.objects.filter(pk=purchase_id).first()
    if not purchase:
        return
    entries = list(
        InventoryLedger.objects.filter(reference_type="purchase", reference_id=purchase.id)
    )
    if not entries:
        return
    total_paid = sum((Decimal(str(e.amount_paid or 0)) for e in entries), Decimal("0.00"))
    total_amt = sum((Decimal(str(e.total_amount or 0)) for e in entries), Decimal("0.00"))
    if total_amt > Decimal("0"):
        purchase.total_amount = total_amt
    purchase.amount_paid = total_paid
    statuses = {e.payment_status for e in entries}
    if statuses == {"Paid"}:
        explicit = "Paid"
    elif "Paid" in statuses or "Partially Paid" in statuses or total_paid > Decimal("0"):
        explicit = "Partially Paid"
    else:
        explicit = "Pending"
    purchase.recompute_payment_fields(explicit_status=explicit)
    purchase.save(
        update_fields=["total_amount", "amount_paid", "amount_due", "payment_status", "updated_at"]
    )


@transaction.atomic
def record_ledger_payment(ledger_entry, data, user=None):
    """
    Record a payment or update payment status on an InventoryLedger entry.
    Supports:
    - paymentAmount / amount: Incremental payment amount to add & log as InventoryPayment
    - totalAmount / total_amount: Optional override of total bill amount for the ledger entry
    - amountPaid / amount_paid: Optional direct total paid amount override
    - paymentStatus / payment_status: Explicit status ('Pending', 'Partially Paid', 'Paid')
    - paymentDate / payment_date, paymentMethod / payment_method, bankAccountId / bank_account,
      referenceNumber / reference_number, notes
    """
    from factory.inventory.ledger.models import InventoryLedger, InventoryPayment
    from factory.inventory.purchase.models import InventoryPurchase
    from factory.bank_account.models import BankAccount

    entry = InventoryLedger.objects.select_for_update().get(pk=ledger_entry.pk)

    raw_total = data.get("totalAmount", data.get("total_amount"))
    if raw_total not in (None, ""):
        entry.total_amount = Decimal(str(raw_total)).quantize(Decimal("0.01"))
    elif Decimal(str(entry.total_amount or 0)) == Decimal("0"):
        qty = entry.quantity_in if entry.quantity_in > 0 else entry.quantity_out
        unit_p = Decimal(str(entry.unit_price or entry.inventory_item.purchase_price or 0))
        if unit_p > 0 and qty > 0:
            entry.unit_price = unit_p.quantize(Decimal("0.01"))
            entry.total_amount = (Decimal(str(qty)) * unit_p).quantize(Decimal("0.01"))

    raw_payment_amount = data.get("paymentAmount", data.get("payment_amount", data.get("amount")))
    payment_amount = (
        Decimal(str(raw_payment_amount)).quantize(Decimal("0.01"))
        if raw_payment_amount not in (None, "")
        else Decimal("0.00")
    )

    raw_amount_paid = data.get("amountPaid", data.get("amount_paid"))
    explicit_status = data.get("paymentStatus", data.get("payment_status"))

    if payment_amount > Decimal("0"):
        entry.amount_paid = Decimal(str(entry.amount_paid or 0)) + payment_amount
    elif raw_amount_paid not in (None, ""):
        entry.amount_paid = Decimal(str(raw_amount_paid)).quantize(Decimal("0.01"))
    elif explicit_status == "Paid" and Decimal(str(entry.total_amount or 0)) > Decimal("0") and Decimal(str(entry.amount_paid or 0)) == Decimal("0"):
        # If user marks status as Paid without entering a separate incremental amount, mark full amount as paid
        entry.amount_paid = Decimal(str(entry.total_amount)).quantize(Decimal("0.01"))
        payment_amount = entry.amount_paid
    elif explicit_status == "Pending" and payment_amount == Decimal("0") and raw_amount_paid in (None, ""):
        entry.amount_paid = Decimal("0.00")

    # Auto-derive status when a payment amount is made unless explicit_status overrides sensibly
    if payment_amount > Decimal("0"):
        if Decimal(str(entry.total_amount or 0)) > Decimal("0") and entry.amount_paid >= entry.total_amount:
            final_status = "Paid"
        else:
            final_status = explicit_status if explicit_status in ("Paid", "Partially Paid") else "Partially Paid"
    else:
        final_status = explicit_status

    entry.recompute_payment_fields(explicit_status=final_status)
    entry.save(
        update_fields=[
            "unit_price",
            "total_amount",
            "amount_paid",
            "amount_due",
            "payment_status",
        ]
    )

    payment_obj = None
    if payment_amount > Decimal("0"):
        bank_id = data.get("bankAccountId", data.get("bank_account", data.get("bank_account_id")))
        bank_account = BankAccount.objects.filter(pk=bank_id).first() if bank_id else None

        purchase_obj = None
        if entry.reference_type == "purchase" and entry.reference_id:
            purchase_obj = InventoryPurchase.objects.filter(pk=entry.reference_id).first()

        pay_date = data.get("paymentDate", data.get("payment_date")) or timezone.localdate()
        pay_method = data.get("paymentMethod", data.get("payment_method")) or "Cash"
        ref_num = data.get("referenceNumber", data.get("reference_number")) or ""
        notes = data.get("notes") or ""

        payment_obj = InventoryPayment.objects.create(
            ledger_entry=entry,
            purchase=purchase_obj,
            supplier=entry.supplier or (purchase_obj.supplier if purchase_obj else entry.inventory_item.preferred_supplier),
            bank_account=bank_account,
            amount=payment_amount,
            payment_date=pay_date,
            payment_method=pay_method,
            reference_number=ref_num,
            notes=notes,
            created_by=user if user and user.is_authenticated else None,
        )

    if entry.reference_type == "purchase" and entry.reference_id:
        _sync_purchase_from_ledger_entries(entry.reference_id)

    return entry, payment_obj


@transaction.atomic
def record_purchase_payment(purchase, data, user=None):
    """
    Record a payment or update payment status on an InventoryPurchase,
    and sync any associated InventoryLedger entries.
    """
    from factory.inventory.purchase.models import InventoryPurchase
    from factory.inventory.ledger.models import InventoryLedger, InventoryPayment
    from factory.bank_account.models import BankAccount

    po = InventoryPurchase.objects.select_for_update().get(pk=purchase.pk)

    raw_payment_amount = data.get("paymentAmount", data.get("payment_amount", data.get("amount")))
    payment_amount = (
        Decimal(str(raw_payment_amount)).quantize(Decimal("0.01"))
        if raw_payment_amount not in (None, "")
        else Decimal("0.00")
    )
    raw_amount_paid = data.get("amountPaid", data.get("amount_paid"))
    explicit_status = data.get("paymentStatus", data.get("payment_status"))

    if payment_amount > Decimal("0"):
        po.amount_paid = Decimal(str(po.amount_paid or 0)) + payment_amount
    elif raw_amount_paid not in (None, ""):
        po.amount_paid = Decimal(str(raw_amount_paid)).quantize(Decimal("0.01"))
    elif explicit_status == "Paid" and Decimal(str(po.total_amount or 0)) > Decimal("0") and Decimal(str(po.amount_paid or 0)) == Decimal("0"):
        po.amount_paid = Decimal(str(po.total_amount)).quantize(Decimal("0.01"))
        payment_amount = po.amount_paid
    elif explicit_status == "Pending" and payment_amount == Decimal("0") and raw_amount_paid in (None, ""):
        po.amount_paid = Decimal("0.00")

    if payment_amount > Decimal("0"):
        if Decimal(str(po.total_amount or 0)) > Decimal("0") and po.amount_paid >= po.total_amount:
            final_status = "Paid"
        else:
            final_status = explicit_status if explicit_status in ("Paid", "Partially Paid") else "Partially Paid"
    else:
        final_status = explicit_status

    po.recompute_payment_fields(explicit_status=final_status)
    po.save(update_fields=["amount_paid", "amount_due", "payment_status", "updated_at"])

    # Sync associated ledger entries proportionally
    entries = list(
        InventoryLedger.objects.filter(reference_type="purchase", reference_id=po.id).order_by("id")
    )
    if entries:
        remaining = Decimal(str(po.amount_paid or 0))
        po_total = Decimal(str(po.total_amount or 0))
        for idx, entry in enumerate(entries):
            e_total = Decimal(str(entry.total_amount or 0))
            if po_total > Decimal("0") and remaining > Decimal("0"):
                if idx == len(entries) - 1:
                    e_paid = min(e_total, max(Decimal("0.00"), remaining))
                else:
                    e_paid = min(
                        e_total,
                        ((e_total / po_total) * Decimal(str(po.amount_paid))).quantize(Decimal("0.01")),
                    )
                remaining -= e_paid
            elif po.payment_status == "Paid":
                e_paid = e_total
            else:
                e_paid = Decimal("0.00")
            entry.amount_paid = e_paid
            entry.recompute_payment_fields(
                explicit_status="Paid" if po.payment_status == "Paid" else None
            )
            entry.save(update_fields=["amount_paid", "amount_due", "payment_status"])

    payment_obj = None
    if payment_amount > Decimal("0"):
        bank_id = data.get("bankAccountId", data.get("bank_account", data.get("bank_account_id")))
        bank_account = BankAccount.objects.filter(pk=bank_id).first() if bank_id else None
        pay_date = data.get("paymentDate", data.get("payment_date")) or timezone.localdate()
        pay_method = data.get("paymentMethod", data.get("payment_method")) or "Cash"
        ref_num = data.get("referenceNumber", data.get("reference_number")) or ""
        notes = data.get("notes") or ""

        payment_obj = InventoryPayment.objects.create(
            ledger_entry=entries[0] if len(entries) == 1 else None,
            purchase=po,
            supplier=po.supplier,
            bank_account=bank_account,
            amount=payment_amount,
            payment_date=pay_date,
            payment_method=pay_method,
            reference_number=ref_num,
            notes=notes,
            created_by=user if user and user.is_authenticated else None,
        )

    return po, payment_obj


