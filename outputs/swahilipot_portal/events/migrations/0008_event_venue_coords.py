from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0007_eventcheckin"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="venue_latitude",
            field=models.DecimalField(
                max_digits=10, decimal_places=7,
                null=True, blank=True,
                help_text="Venue GPS latitude — required for geofence check-in enforcement.",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="venue_longitude",
            field=models.DecimalField(
                max_digits=10, decimal_places=7,
                null=True, blank=True,
                help_text="Venue GPS longitude — required for geofence check-in enforcement.",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="venue_radius_meters",
            field=models.PositiveIntegerField(
                default=200,
                help_text="Allowed radius from venue centre for geofence check-in (metres).",
            ),
        ),
    ]
