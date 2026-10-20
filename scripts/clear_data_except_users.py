import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_setup = False
import django
django.setup()

from django.db import transaction, connection
from django.apps import apps
from accounts.models import User, Role

# Models that should be cleared (all operational & factory data, logs, sessions)
CLEAR_APP_LABELS = {'factory', 'audit_logs'}
ADDITIONAL_MODELS = {'admin.LogEntry', 'sessions.Session'}

def run_clear():
    # Identify target models
    target_models = []
    
    # Add factory & audit_logs models
    for model in apps.get_models():
        if model._meta.app_label in CLEAR_APP_LABELS or model._meta.label in ADDITIONAL_MODELS:
            target_models.append(model)
            
    print(f"Found {len(target_models)} models to clear.")
    
    # Topological / dependency-safe order: child models first
    # Order deletion
    deletion_order = [
        # 1. Cloth Stock & Patches (leaf nodes)
        'factory.CleanClothStock',
        'factory.DefectedClothStock',
        'factory.ClothPatch',
        'factory.ClothStock',
        'factory.ClothName',
        
        # 2. Production & Loom operations
        'factory.Production',
        'factory.BeamDismountReconciliation',
        'factory.BeamLoading',
        
        # 3. Sizing outcomes & assignments (depend on YarnOutcome and Beam)
        'factory.SizingBeamAssignment',
        'factory.SizingOutcome',
        
        # 4. Yarn outcomes (depend on Sizing, YarnStock, YarnIntake, YarnBuyer)
        'factory.YarnOutcomeItem',
        'factory.YarnOutcome',
        
        # 5. Sizing & Beams & Looms (now safe to delete)
        'factory.Beam',
        'factory.Loom',
        'factory.Sizing',
        
        # 6. Yarn intake & stock & yarn attributes
        'factory.YarnIntake',
        'factory.YarnStock',
        'factory.YarnBuyer',
        'factory.YarnCount',
        'factory.YarnType',
        'factory.YarnName',
        
        # 7. Suppliers & Customers
        'factory.SupplierBankAccount',
        'factory.Supplier',
        'factory.CustomerBankAccount',
        'factory.Customer',
        
        # 8. Activity Logs, Admin Logs, Sessions
        'audit_logs.ActivityLog',
        'admin.LogEntry',
        'sessions.Session',
    ]
    
    # Verify all target models are included in deletion_order
    for m in target_models:
        if m._meta.label not in deletion_order:
            deletion_order.insert(0, m._meta.label)

    print("\nStarting data clearance inside transaction...")
    summary = {}
    with transaction.atomic():
        for label in deletion_order:
            try:
                model = apps.get_model(label)
                count = model.objects.count()
                if count > 0:
                    deleted_count, _ = model.objects.all().delete()
                    summary[label] = deleted_count
                    print(f"  [CLEARED] {label}: {deleted_count} record(s)")
                else:
                    summary[label] = 0
                    print(f"  [EMPTY]   {label}: 0 records")
            except LookupError:
                print(f"  [SKIP]    {label}: Model not found")

        # Reset sequences for cleared tables in PostgreSQL
        print("\nResetting primary key sequences...")
        with connection.cursor() as cursor:
            for label in deletion_order:
                try:
                    model = apps.get_model(label)
                    table = model._meta.db_table
                    pk_col = model._meta.pk.column
                    cursor.execute(f"SELECT pg_get_serial_sequence('{table}', '{pk_col}');")
                    res = cursor.fetchone()
                    if res and res[0]:
                        seq = res[0]
                        cursor.execute(f"ALTER SEQUENCE {seq} RESTART WITH 1;")
                        print(f"  Reset sequence for {table} ({seq})")
                except Exception as e:
                    print(f"  Could not reset sequence for {label}: {e}")

    print("\nDatabase data cleared successfully!")
    print("\nPreserved Users:")
    for u in User.objects.all():
        role_name = u.role.name if u.role else "No Role"
        print(f"  - Username: {u.username} | Email: {u.email} | Superuser: {u.is_superuser} | Role: {role_name}")

    print("\nPreserved Roles:")
    for r in Role.objects.all():
        print(f"  - Role: {r.name} (System: {r.is_system})")

if __name__ == '__main__':
    run_clear()
