# Generated migration to remove beam and loom foreign keys from Production model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("factory", "0020_sizingbeamassignment_beam_yarn_length"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="production",
            name="beam",
        ),
        migrations.RemoveField(
            model_name="production",
            name="loom",
        ),
    ]
