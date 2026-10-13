import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.apps import apps
from accounts.models import User

# List of all project models to clear
models_to_clear = [
    'factory.Production',
    'factory.BeamLoading',
    'factory.SizingBeamAssignment',
    'factory.SizingOutcome',
    'factory.YarnOutcome',
    'factory.YarnIntake',
    'factory.YarnStock',
    'factory.Sizing',
    'factory.Beam',
    'factory.Loom',
    'factory.SupplierBankAccount',
    'factory.Supplier',
    'factory.CustomerBankAccount',
    'factory.Customer',
    'factory.YarnBuyer',
    'audit_logs.ActivityLog',
    'admin.LogEntry',
    'sessions.Session',
    'accounts.Role',
]

with transaction.atomic():
    for label in models_to_clear:
        model = apps.get_model(label)
        deleted_count, _ = model.objects.all().delete()
        print(f"Cleared {label}: {deleted_count} record(s)")

    non_super_deleted, _ = User.objects.filter(is_superuser=False).delete()
    print(f"Cleared non-superuser User(s): {non_super_deleted} record(s)")

print("\nDatabase cleared successfully except superusers!")
print("Remaining superuser(s):", [(u.username, u.email, u.is_superuser) for u in User.objects.all()])
