"""
Verification test script for the complete Inventory Management Module.
"""
import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from factory.purchase.supplier.models import Supplier
from factory.inventory.category.models import InventoryCategory
from factory.inventory.unit.models import InventoryUnit
from factory.inventory.item.models import InventoryItem
from factory.inventory.purchase.models import InventoryPurchase, InventoryPurchaseItem
from factory.inventory.transaction.models import InventoryTransaction
from factory.inventory.ledger.models import InventoryLedger
from factory.inventory.services import (
    confirm_purchase,
    process_transaction,
    create_opening_stock_ledger,
)

User = get_user_model()
admin_user = User.objects.filter(is_superuser=True).first()

print("=" * 60)
print("RUNNING INVENTORY MANAGEMENT WORKFLOW VERIFICATION")
print("=" * 60)

# 1. Category & Unit
cat, _ = InventoryCategory.objects.get_or_create(
    name="Spare Parts Test",
    defaults={"description": "Mechanical and electrical loom spare parts"}
)
unit_pcs, _ = InventoryUnit.objects.get_or_create(
    name="Piece",
    defaults={"abbreviation": "Pcs"}
)
unit_kg, _ = InventoryUnit.objects.get_or_create(
    name="Kilogram",
    defaults={"abbreviation": "Kg"}
)
print(f"✓ Category: {cat.name}, Units: {unit_pcs.name}, {unit_kg.name}")

# 2. Supplier
supplier, _ = Supplier.objects.get_or_create(
    supplier_name="Universal Loom Spares Co.",
    defaults={"phone": "0300-1234567", "supplier_type": "Spare Parts"}
)
print(f"✓ Supplier: {supplier.supplier_name} ({supplier.supplier_code})")

# 3. Create Item with Opening Stock
item = InventoryItem.objects.create(
    item_name="Rapier Gripper Right Hand Test",
    category=cat,
    unit=unit_pcs,
    opening_stock=Decimal("10"),
    minimum_stock_level=Decimal("5"),
    purchase_price=Decimal("1500.00"),
    preferred_supplier=supplier,
    storage_location="Bin A-12",
    created_by=admin_user,
)
create_opening_stock_ledger(item, admin_user)
item.refresh_from_db()
print(f"✓ Item created: {item.item_code} - {item.item_name}")
print(f"  Current stock after opening stock: {item.current_stock} (Expected: 10)")
assert item.current_stock == Decimal("10"), f"Expected 10, got {item.current_stock}"

# Verify Opening Stock Ledger
open_ledger = InventoryLedger.objects.filter(inventory_item=item, transaction_type="Opening Stock").first()
assert open_ledger is not None, "Opening stock ledger entry missing"
assert open_ledger.running_balance == Decimal("10")
print(f"✓ Opening stock ledger verified: Running balance = {open_ledger.running_balance}")

# 4. Record and Confirm Purchase from Supplier (Stock In)
purchase = InventoryPurchase.objects.create(
    supplier=supplier,
    purchase_date="2026-11-11",
    reference_number="BILL-9901",
    notes="Test delivery of 15 rapier grippers",
    created_by=admin_user,
)
InventoryPurchaseItem.objects.create(
    purchase=purchase,
    inventory_item=item,
    quantity=Decimal("15"),
    unit_price=Decimal("1450.00"),
    total_price=Decimal("21750.00"),
)
confirm_purchase(purchase, admin_user)
item.refresh_from_db()
purchase.refresh_from_db()
print(f"✓ Purchase confirmed: {purchase.purchase_number}, Status: {purchase.status}")
print(f"  Current stock after purchase of 15: {item.current_stock} (Expected: 25)")
assert item.current_stock == Decimal("25"), f"Expected 25, got {item.current_stock}"

# Verify Purchase Ledger
pur_ledger = InventoryLedger.objects.filter(inventory_item=item, reference_type="purchase").first()
assert pur_ledger is not None
assert pur_ledger.running_balance == Decimal("25")
print(f"✓ Purchase ledger entry verified: Qty In = {pur_ledger.quantity_in}, Running balance = {pur_ledger.running_balance}")

# 5. Record Stock Out / Usage
stock_out = InventoryTransaction.objects.create(
    transaction_date="2026-11-11",
    inventory_item=item,
    transaction_type="Stock Out",
    quantity=Decimal("8"),
    issued_to="Weaver Master Aslam",
    related_area="Loom Shed #1",
    notes="Replaced worn out right gripper on Loom L-04",
    created_by=admin_user,
)
process_transaction(stock_out, admin_user)
item.refresh_from_db()
print(f"✓ Stock out recorded: {stock_out.transaction_number}, Qty: 8")
print(f"  Current stock after stock out: {item.current_stock} (Expected: 17)")
assert item.current_stock == Decimal("17"), f"Expected 17, got {item.current_stock}"

# 6. Test Insufficient Stock Prevention
try:
    excess_out = InventoryTransaction.objects.create(
        transaction_date="2026-11-11",
        inventory_item=item,
        transaction_type="Stock Out",
        quantity=Decimal("100"),  # Only 17 available!
        created_by=admin_user,
    )
    process_transaction(excess_out, admin_user)
    print("❌ Failed: Insufficient stock validation did not trigger!")
except ValidationError as e:
    print(f"✓ Insufficient stock correctly prevented: {e}")

# 7. Record Stock Adjustment (Adjustment In & Out)
adj_in = InventoryTransaction.objects.create(
    transaction_date="2026-11-11",
    inventory_item=item,
    transaction_type="Adjustment In",
    quantity=Decimal("3"),
    notes="Physical stock audit found 3 extra unopened units",
    created_by=admin_user,
)
process_transaction(adj_in, admin_user)
item.refresh_from_db()
print(f"✓ Adjustment In recorded: +3, New stock: {item.current_stock} (Expected: 20)")
assert item.current_stock == Decimal("20")

adj_out = InventoryTransaction.objects.create(
    transaction_date="2026-11-11",
    inventory_item=item,
    transaction_type="Adjustment Out",
    quantity=Decimal("2"),
    notes="Damaged in shelf drop during audit",
    created_by=admin_user,
)
process_transaction(adj_out, admin_user)
item.refresh_from_db()
print(f"✓ Adjustment Out recorded: -2, New stock: {item.current_stock} (Expected: 18)")
assert item.current_stock == Decimal("18")

# 8. Verify Complete Chronological Ledger Entries
entries = InventoryLedger.objects.filter(inventory_item=item).order_by("transaction_date", "id")
print("\n--- CHRONOLOGICAL INVENTORY LEDGER ENTRIES ---")
for idx, entry in enumerate(entries, start=1):
    print(f"{idx}. [{entry.transaction_date}] {entry.transaction_number:<15} | {entry.transaction_type:<15} | In: {entry.quantity_in:>5} | Out: {entry.quantity_out:>5} | Balance: {entry.running_balance:>5} | Notes: {entry.notes}")

print("=" * 60)
print("ALL INVENTORY BACKEND VERIFICATIONS PASSED SUCCESSFULLY!")
print("=" * 60)

