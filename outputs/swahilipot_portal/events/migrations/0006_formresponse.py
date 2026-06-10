from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0005_event_qr_uuid"),
    ]

    operations = [
        migrations.CreateModel(
            name="FormResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("respondent_name",  models.CharField(blank=True, max_length=220)),
                ("respondent_email", models.CharField(blank=True, max_length=254)),
                ("respondent_phone", models.CharField(blank=True, max_length=50)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="form_responses",
                        to="events.event",
                    ),
                ),
            ],
            options={"ordering": ("-submitted_at",)},
        ),
    ]
