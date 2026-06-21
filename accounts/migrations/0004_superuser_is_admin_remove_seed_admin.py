from django.db import migrations


def use_superuser_as_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).update(role="admin", is_staff=True)
    superusers = User.objects.filter(is_superuser=True).order_by("id")
    primary_admin = superusers.first()
    if primary_admin:
        User.objects.filter(username="portal_admin").exclude(pk=primary_admin.pk).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_admin_role_full_access"),
    ]

    operations = [
        migrations.RunPython(use_superuser_as_admin, noop_reverse),
    ]
