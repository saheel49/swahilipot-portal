import uuid
from django.db import migrations, models


def populate_qr_uuid(apps, schema_editor):
    """Give every existing event a unique UUID."""
    Event = apps.get_model("events", "Event")
    for event in Event.objects.all():
        event.qr_uuid = uuid.uuid4()
        event.save(update_fields=["qr_uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0004_event_form_response_count"),
    ]

    operations = [
        # Step 1: add the column without unique constraint, nullable so existing rows get NULL
        migrations.AddField(
            model_name="event",
            name="qr_uuid",
            field=models.UUIDField(null=True, blank=True, editable=False),
        ),
        # Step 2: populate UUIDs on existing rows
        migrations.RunPython(populate_qr_uuid, migrations.RunPython.noop),
        # Step 3: alter to non-null + unique now that every row has a value
        migrations.AlterField(
            model_name="event",
            name="qr_uuid",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
