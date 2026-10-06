import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from factory.beam.models import Beam
from factory.loom.models import Loom

for i in range(1, 6):
    Loom.objects.create(
        loom_code=f'L-{i:03d}',
        loom_name=f'Loom {i}',
        model_number=f'MDL-{i}',
        width=120.0
    )
    Beam.objects.create(
        beam_number=f'B-{i:03d}',
        beam_name=f'Beam {i}',
        yarn_count='40s',
        warp_count=1000,
        total_ends=4000,
        length=2000.0,
        weight=50.0
    )

print("5 Beams and 5 Looms created.")
