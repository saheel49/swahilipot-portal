from django.db import migrations


def grant_admin_role_full_access(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="admin").update(is_staff=True, is_superuser=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_user_profile_photo"),
    ]

    operations = [
        migrations.RunPython(grant_admin_role_full_access, noop_reverse),
    ]
