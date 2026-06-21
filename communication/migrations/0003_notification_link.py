from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0002_notification_priority"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="link",
            field=models.CharField(
                blank=True,
                max_length=500,
                help_text=(
                    "Optional URL this notification links to. "
                    "If set, clicking the notification navigates there."
                ),
            ),
        ),
    ]
