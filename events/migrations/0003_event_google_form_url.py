from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_alter_event_banner_alter_event_qr_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="google_form_url",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Auto-generated Google Form URL. "
                    "Override with a custom form URL if needed. "
                    "The QR code will point to this URL."
                ),
            ),
        ),
    ]
