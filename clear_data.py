import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.apps import apps

# Models that MUST BE PRESERVED
PRESERVE_MODELS = {
    'accounts.user',
    'accounts.role',
    'factory.yarnname',
    'factory.yarntype',
    'factory.yarncount',
}

# Apps whose data should be cleared (except the preserved models)
APPS_TO_CLEAR = {'factory', 'audit_logs'}

print("Starting data purge...")

with transaction.atomic():
    cleared_summary = {}

    # Gather models to clear
    models_to_clear = []
    for app_label in APPS_TO_CLEAR:
        app_config = apps.get_app_config(app_label)
        for model in app_config.get_models():
            label = model._meta.label_lower
            if label not in PRESERVE_MODELS:
                models_to_clear.append(model)

    # Sort or repeatedly delete until all child/parent dependencies are resolved
    max_passes = 5
    for pass_num in range(max_passes):
        deleted_in_pass = 0
        for model in models_to_clear:
            try:
                count = model.objects.count()
                if count > 0:
                    deleted_count, _ = model.objects.all().delete()
                    cleared_summary[model._meta.label] = cleared_summary.get(model._meta.label, 0) + deleted_count
                    deleted_in_pass += deleted_count
            except Exception as e:
                # Dependency might need child deleted first, will be caught on next pass
                pass
        if deleted_in_pass == 0:
            break

    # Also clear admin LogEntry and Session if any
    try:
        from django.contrib.admin.models import LogEntry
        log_count, _ = LogEntry.objects.all().delete()
        if log_count > 0:
            cleared_summary['admin.LogEntry'] = log_count
    except Exception:
        pass

    try:
        from django.contrib.sessions.models import Session
        sess_count, _ = Session.objects.all().delete()
        if sess_count > 0:
            cleared_summary['sessions.Session'] = sess_count
    except Exception:
        pass

print("\n--- Summary of Cleared Data ---")
for model_label, count in sorted(cleared_summary.items()):
    print(f"Cleared {model_label}: {count} record(s)")

print("\n--- Preserved Data Check ---")
for preserved in sorted(PRESERVE_MODELS):
    model = apps.get_model(preserved)
    print(f"Preserved {model._meta.label}: {model.objects.count()} record(s)")
    if model._meta.label in ['accounts.User']:
        for u in model.objects.all():
            print(f"  - User: {u.username} (email: {u.email}, is_superuser: {u.is_superuser})")
    elif model._meta.label in ['factory.YarnName', 'factory.YarnType', 'factory.YarnCount']:
        for item in model.objects.all()[:10]:
            print(f"  - {model._meta.object_name}: {item}")
