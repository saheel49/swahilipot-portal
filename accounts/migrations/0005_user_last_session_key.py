from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_superuser_is_admin_remove_seed_admin"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_session_key",
            field=models.CharField(blank=True, max_length=40, default=""),
            preserve_default=False,
        ),
    ]
