from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0003_event_google_form_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="form_response_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Number of Google Form responses received for this event. "
                    "Auto-updated via the /events/<pk>/form-response/ webhook "
                    "triggered by Google Apps Script."
                ),
            ),
        ),
    ]
