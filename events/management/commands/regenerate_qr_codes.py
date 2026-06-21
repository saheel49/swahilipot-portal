"""
Management command: regenerate QR codes for all events so they point
to the portal's own /events/qr/<uuid>/ endpoint.

The UUID is stable per event — regenerating the QR never breaks
existing printed codes.

Usage:
    python manage.py regenerate_qr_codes
"""
from django.core.management.base import BaseCommand
from events.models import Event


class Command(BaseCommand):
    help = "Regenerate QR codes for all events (points to portal /events/qr/<uuid>/)"

    def handle(self, *args, **options):
        events = Event.objects.all()
        total = events.count()
        self.stdout.write(f"Processing {total} event(s)...")

        for event in events:
            old_qr = event.qr_code.name if event.qr_code else "(none)"
            event.qr_code = None  # force regeneration
            event.regenerate_qr()
            if event.qr_code:
                Event.objects.filter(pk=event.pk).update(qr_code=event.qr_code.name)
            portal_url = event.get_portal_qr_url()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ [{event.pk}] {event.title}\n"
                    f"    UUID: {event.qr_uuid}\n"
                    f"    QR URL: {portal_url}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"\nDone. {total} QR code(s) regenerated."))
