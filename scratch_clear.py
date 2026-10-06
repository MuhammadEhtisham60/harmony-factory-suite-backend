import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from factory.yarn.intake.models import YarnIntake
from factory.yarn.sizing.models import SizingOutcome, Beam
from factory.yarn.outcomes.models import YarnOutcome

# Delete in order to handle foreign keys, or just delete all
YarnOutcome.objects.filter(outcome_type='Sizing').delete()
SizingOutcome.objects.all().delete()
Beam.objects.all().delete()
YarnIntake.objects.all().delete()

print("Data cleared successfully.")
