"""
Management command to clear all factory, production, inventory, sales, purchase,
and audit log data from the database while strictly preserving User accounts and Roles.
Usage:
    python manage.py clear_factory_data
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from audit_logs.models import ActivityLog
from factory.purchase.supplier.models import Supplier, SupplierBankAccount
from factory.sales.customer.models import Customer, CustomerBankAccount
from factory.loom.models import Loom
from factory.beam.models import Beam, BeamLoading, Production, BeamDismountReconciliation
from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_stock.models import YarnStock
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome, YarnOutcomeItem
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from factory.cloth.models import ClothName, ClothPatch, ClothStock, CleanClothStock, DefectedClothStock
from accounts.models import User, Role


class Command(BaseCommand):
    help = "Clears all factory, inventory, production, sizing, and audit data while preserving Users and Roles."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting database cleanup (preserving Users & Roles)..."))

        # Order matters for foreign keys and cascading integrity (children first, parents last)
        models_to_clear = [
            # 1. Audit Logs
            (ActivityLog, "Activity Logs"),

            # 2. Reconciliations & Productions
            (BeamDismountReconciliation, "Beam Dismount Reconciliations"),
            (Production, "Cloth Productions"),

            # 3. Cloth Stocks & Patches
            (CleanClothStock, "Clean Cloth Stocks"),
            (DefectedClothStock, "Defected Cloth Stocks"),
            (ClothStock, "Cloth Stocks"),
            (ClothPatch, "Cloth Patches"),

            # 4. Beam Loadings & Assignments
            (BeamLoading, "Beam Loadings"),
            (SizingBeamAssignment, "Sizing Beam Assignments"),
            (Beam, "Physical Beams"),

            # 5. Looms
            (Loom, "Looms"),

            # 6. Sizing Outcomes
            (SizingOutcome, "Sizing Outcomes"),

            # 7. Yarn Outcomes, Items, Stocks & Intakes (must be deleted before Sizing, as YarnOutcome.sizing is PROTECT)
            (YarnOutcomeItem, "Yarn Outcome Items"),
            (YarnOutcome, "Yarn Outcomes"),
            (YarnIntake, "Yarn Intakes"),
            (YarnStock, "Yarn Stocks"),

            # 8. Sizing Units
            (Sizing, "Sizing Units"),

            # 9. Master Entities & Specs
            (ClothName, "Cloth Qualities / Names"),
            (YarnName, "Yarn Names"),
            (YarnType, "Yarn Types"),
            (YarnCount, "Yarn Counts"),
            (YarnBuyer, "Yarn Buyers"),

            # 10. Customers & Suppliers
            (CustomerBankAccount, "Customer Bank Accounts"),
            (Customer, "Customers"),
            (SupplierBankAccount, "Supplier Bank Accounts"),
            (Supplier, "Suppliers"),
        ]

        total_deleted = 0
        with transaction.atomic():
            for model_class, display_name in models_to_clear:
                count, _ = model_class.objects.all().delete()
                total_deleted += count
                self.stdout.write(f"  - Cleared {count} records from {display_name}")

        user_count = User.objects.count()
        role_count = Role.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f"\nDatabase cleared successfully! ({total_deleted} total factory/audit records deleted)."
        ))
        self.stdout.write(self.style.NOTICE(
            f"Preserved User accounts: {user_count} | Preserved Roles: {role_count}."
        ))
