"""
Management command: refresh Google Form pre-fill URLs for all events.

This rebuilds every event's google_form_url using the current settings
(GOOGLE_FORM_BASE_URL, GOOGLE_FORM_EVENT_ID_FIELD, GOOGLE_FORM_EVENT_NAME_FIELD).

Run after:
  - Changing any GOOGLE_FORM_* .env variable
  - Upgrading the portal (adds usp=pp_url parameter)

Usage:
    python manage.py refresh_form_urls
"""
from django.core.management.base import BaseCommand
from events.models import Event, build_form_url


class Command(BaseCommand):
    help = "Refresh Google Form pre-fill URLs for all events (rebuilds with current .env settings)"

    def handle(self, *args, **options):
        events = Event.objects.all()
        total = events.count()
        self.stdout.write(f"Processing {total} event(s)...")

        updated = 0
        for event in events:
            new_url = build_form_url(event)
            if new_url and new_url != event.google_form_url:
                Event.objects.filter(pk=event.pk).update(google_form_url=new_url)
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ [{event.pk}] {event.title}\n"
                        f"    New URL: {new_url[:80]}..."
                    )
                )
            else:
                self.stdout.write(f"  - [{event.pk}] {event.title} — unchanged")

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {updated}/{total} event URL(s) updated.")
        )
