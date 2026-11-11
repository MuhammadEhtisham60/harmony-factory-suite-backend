"""
Business-logic services for the Inventory module.

All stock mutations go through these functions to ensure atomicity,
correct ledger creation, and running-balance maintenance.
"""

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError


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
            reference_type="opening",
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

    for item_line in purchase.items.select_related("inventory_item").all():
        inv_item = InventoryItem.objects.select_for_update().get(
            pk=item_line.inventory_item_id
        )
        prev_balance = get_last_running_balance(inv_item.id)
        new_balance = prev_balance + item_line.quantity

        InventoryLedger.objects.create(
            inventory_item=inv_item,
            transaction_date=purchase.purchase_date,
            transaction_number=f"{purchase.purchase_number}-{item_line.id}",
            transaction_type="Stock In",
            quantity_in=item_line.quantity,
            quantity_out=Decimal("0"),
            running_balance=new_balance,
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
    purchase.save(update_fields=["status"])


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

    InventoryLedger.objects.create(
        inventory_item=inv_item,
        transaction_date=inv_transaction.transaction_date,
        transaction_number=inv_transaction.transaction_number,
        transaction_type=inv_transaction.transaction_type,
        quantity_in=qty_in,
        quantity_out=qty_out,
        running_balance=new_balance,
        reference_id=inv_transaction.id,
        reference_type="transaction",
        notes=inv_transaction.notes,
        created_by=created_by,
    )
    inv_item.current_stock = new_balance
    inv_item.save(update_fields=["current_stock"])
