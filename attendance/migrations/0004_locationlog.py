from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0003_geofenceviolation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LocationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("turned_off_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("turned_on_at", models.DateTimeField(blank=True, null=True)),
                ("duration_minutes", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    help_text="Minutes location was off (filled when turned back on)",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="location_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ("-turned_off_at",)},
        ),
    ]
