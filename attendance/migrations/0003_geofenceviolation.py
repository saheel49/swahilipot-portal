from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0002_attendance_arrival_status_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GeofenceViolation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("detected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("latitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("longitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("distance_meters", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "resolution",
                    models.CharField(
                        choices=[("open", "Open"), ("acknowledged", "Acknowledged"), ("dismissed", "Dismissed")],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("management_alerted", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                (
                    "attendance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="violations",
                        to="attendance.attendance",
                    ),
                ),
                (
                    "project_site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="attendance.projectsite"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="geofence_violations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-detected_at",),
            },
        ),
    ]
