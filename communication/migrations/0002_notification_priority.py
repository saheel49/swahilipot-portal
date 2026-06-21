from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="priority",
            field=models.CharField(
                choices=[
                    ("low",      "Low"),
                    ("medium",   "Medium"),
                    ("high",     "High"),
                    ("critical", "Critical"),
                ],
                default="low",
                max_length=10,
            ),
        ),
    ]
