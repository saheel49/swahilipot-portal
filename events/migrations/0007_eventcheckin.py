from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0006_formresponse"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventCheckIn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_in_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("latitude",  models.DecimalField(max_digits=10, decimal_places=7)),
                ("longitude", models.DecimalField(max_digits=10, decimal_places=7)),
                ("distance_meters", models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_checkins",
                        to="events.event",
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_checkins",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-checked_in_at",),
                "unique_together": {("event", "participant")},
            },
        ),
    ]
