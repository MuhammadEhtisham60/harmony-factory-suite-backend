from django.db import migrations, models
import django.db.models.deletion


def backfill_dispatch_marker(apps, schema_editor):
    """
    Beams already out at sizing through an old dispatch-time assignment get the
    new marker so deleting that dispatch resets them automatically.
    """
    SizingBeamAssignment = apps.get_model("factory", "SizingBeamAssignment")
    for assignment in SizingBeamAssignment.objects.filter(status="ASSIGNED"):
        assignment.beam.filter(status="Sizing", dispatched_yarn_outcome__isnull=True).update(
            dispatched_yarn_outcome_id=assignment.yarn_outcome_id
        )


class Migration(migrations.Migration):

    dependencies = [
        ("factory", "0043_yarnintake_outcome_total_rate_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="beam",
            name="dispatched_yarn_outcome",
            field=models.ForeignKey(
                blank=True,
                help_text="Yarn outcome (sizing dispatch) this beam is currently out at sizing for",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dispatched_beams",
                to="factory.yarnoutcome",
            ),
        ),
        migrations.RunPython(backfill_dispatch_marker, migrations.RunPython.noop),
    ]
