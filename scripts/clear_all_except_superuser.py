import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import transaction, connection
from django.apps import apps
from accounts.models import User, Role

def run():
    print("Starting database cleanup: keeping only superuser...")
    with transaction.atomic():
        # 1. Clear any remaining factory models, audit logs, admin log, sessions
        clear_labels = [
            'factory.CleanClothStock',
            'factory.DefectedClothStock',
            'factory.ClothPatch',
            'factory.ClothStock',
            'factory.ClothName',
            'factory.Production',
            'factory.BeamDismountReconciliation',
            'factory.BeamLoading',
            'factory.SizingBeamAssignment',
            'factory.SizingOutcome',
            'factory.YarnOutcomeItem',
            'factory.YarnOutcome',
            'factory.Beam',
            'factory.Loom',
            'factory.Sizing',
            'factory.YarnIntake',
            'factory.YarnStock',
            'factory.YarnBuyer',
            'factory.YarnCount',
            'factory.YarnType',
            'factory.YarnName',
            'factory.SupplierBankAccount',
            'factory.Supplier',
            'factory.CustomerBankAccount',
            'factory.Customer',
            'audit_logs.ActivityLog',
            'admin.LogEntry',
            'sessions.Session',
        ]
        for label in clear_labels:
            try:
                model = apps.get_model(label)
                deleted, _ = model.objects.all().delete()
                if deleted:
                    print(f"Cleared {label}: {deleted} records")
            except Exception as e:
                print(f"Error checking {label}: {e}")

        # 2. Clear non-superuser accounts
        non_super_deleted, _ = User.objects.filter(is_superuser=False).delete()
        print(f"Cleared non-superuser User(s): {non_super_deleted} record(s)")

        # 3. Clear all roles
        roles_deleted, _ = Role.objects.all().delete()
        print(f"Cleared Role(s): {roles_deleted} record(s)")

        # 4. Reset sequences for cleared tables & roles
        tables_to_reset = [
            'accounts_role',
            'audit_logs_activitylog',
            'django_admin_log',
            'factory_cleanclothstock',
            'factory_defectedclothstock',
            'factory_clothpatch',
            'factory_clothstock',
            'factory_clothname',
            'factory_production',
            'factory_beamdismountreconciliation',
            'factory_beamloading',
            'factory_sizingbeamassignment',
            'factory_sizingoutcome',
            'factory_yarnoutcomeitem',
            'factory_yarnoutcome',
            'factory_beam',
            'factory_loom',
            'factory_sizing',
            'factory_yarnintake',
            'factory_yarnstock',
            'factory_yarnbuyer',
            'factory_yarncount',
            'factory_yarntype',
            'factory_yarnname',
            'factory_supplierbankaccount',
            'factory_supplier',
            'factory_customerbankaccount',
            'factory_customer',
        ]
        with connection.cursor() as cursor:
            for tbl in tables_to_reset:
                try:
                    cursor.execute(f"SELECT pg_get_serial_sequence('{tbl}', 'id');")
                    res = cursor.fetchone()
                    if res and res[0]:
                        cursor.execute(f"ALTER SEQUENCE {res[0]} RESTART WITH 1;")
                except Exception as e:
                    pass

    print("\nCleanup completed successfully!")
    print("\nRemaining Users in Database:")
    for u in User.objects.all():
        print(f"  - ID: {u.id} | Username: {u.username} | Email: {u.email} | Superuser: {u.is_superuser} | Staff: {u.is_staff} | Active: {u.is_active}")

    print("\nRemaining Roles in Database:")
    print(f"  Total roles: {Role.objects.count()}")

if __name__ == '__main__':
    run()
