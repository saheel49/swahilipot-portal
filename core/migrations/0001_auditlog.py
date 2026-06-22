from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("username_snapshot", models.CharField(blank=True, max_length=150)),
                ("action", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("category", models.CharField(
                    choices=[
                        ("auth", "Authentication"),
                        ("attendance", "Attendance"),
                        ("tasks", "Tasks"),
                        ("users", "Users & Accounts"),
                        ("departments", "Departments"),
                        ("events", "Events"),
                        ("communication", "Communication"),
                        ("suggestions", "Suggestions"),
                        ("reports", "Reports"),
                        ("system", "System"),
                        ("other", "Other"),
                    ],
                    default="other",
                    max_length=30,
                )),
                ("severity", models.CharField(
                    choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")],
                    default="info",
                    max_length=10,
                )),
                ("method", models.CharField(blank=True, max_length=10)),
                ("path", models.CharField(blank=True, max_length=500)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("object_type", models.CharField(blank=True, max_length=80)),
                ("object_id", models.CharField(blank=True, max_length=40)),
                ("object_repr", models.CharField(blank=True, max_length=200)),
                ("timestamp", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-timestamp",)},
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user", "-timestamp"], name="core_audit_user_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["category", "-timestamp"], name="core_audit_cat_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action", "-timestamp"], name="core_audit_act_ts_idx"),
        ),
    ]
