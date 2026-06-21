"""
Management command: python manage.py regenerate_all_qr

Regenerates QR codes for all events using the current SITE_BASE_URL from .env.
Run this after updating DJANGO_SITE_BASE_URL (e.g. after ngrok URL changes).

Usage:
    python manage.py regenerate_all_qr
"""

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Regenerate QR codes for all events using the current SITE_BASE_URL"

    def handle(self, *args, **options):
        from events.models import Event

        base_url = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000")
        self.stdout.write(f"\nRegenerating QR codes using base URL: {base_url}\n")

        events = Event.objects.all()
        if not events.exists():
            self.stdout.write(self.style.WARNING("No events found.\n"))
            return

        count = 0
        for event in events:
            try:
                event.regenerate_qr()
                if event.qr_code:
                    Event.objects.filter(pk=event.pk).update(
                        qr_code=event.qr_code.name,
                        google_form_url=event.google_form_url,
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ {event.title}"))
                    count += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠ {event.title} — qrcode package not installed, skipped"
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {event.title} — {e}"))

        self.stdout.write(f"\nDone. {count}/{events.count()} QR codes regenerated.\n")
        self.stdout.write(self.style.WARNING(
            "Tip: if you changed DJANGO_SITE_BASE_URL, restart the server too.\n"
        ))
