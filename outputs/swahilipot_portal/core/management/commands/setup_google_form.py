"""
Management command: python manage.py setup_google_form

Walks you through setting up Google Form pre-fill so the Event ID and Event
Name auto-fill when someone scans a QR code.

Steps it handles:
  1. You paste a pre-filled link you generated from Google Forms
  2. It extracts the entry.XXXXXXXXX field keys automatically
  3. It writes them into your .env file
  4. It regenerates all QR codes with the new pre-fill baked in

Usage:
    python manage.py setup_google_form
"""

import re
import urllib.parse
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Set up Google Form pre-fill field IDs from a pre-filled link"

    def handle(self, *args, **options):
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS("  Google Form Pre-fill Setup"))
        self.stdout.write("═" * 60 + "\n")

        self.stdout.write(
            "This command reads the entry.XXXXXXXXX field keys from a\n"
            "pre-filled Google Form link and writes them to your .env.\n\n"
            "How to get a pre-filled link:\n"
            "  1. Open your Google Form\n"
            "  2. Click ⋮ (three dots top-right) → 'Get pre-filled link'\n"
            "  3. Type any text in the Event ID field (e.g. 'TEST')\n"
            "  4. Optionally type something in the Event Name field too\n"
            "  5. Click 'Get link' → copy the full URL → paste it below\n\n"
        )

        prefilled_url = input("Paste your pre-filled Google Form URL here:\n> ").strip()

        if not prefilled_url:
            self.stdout.write(self.style.ERROR("No URL provided. Aborting.\n"))
            return

        # Extract the base URL (up to /viewform)
        base_match = re.match(r"(https://docs\.google\.com/forms/d/e/[^/]+/viewform)", prefilled_url)
        if not base_match:
            self.stdout.write(self.style.ERROR(
                "Could not find a Google Form URL in that input.\n"
                "It should start with: https://docs.google.com/forms/d/e/...\n"
            ))
            return

        base_url = base_match.group(1)
        self.stdout.write(self.style.SUCCESS(f"\n✓ Base URL: {base_url}"))

        # Parse query params to find entry.XXXXXXXXX keys
        parsed = urllib.parse.urlparse(prefilled_url)
        params = urllib.parse.parse_qs(parsed.query)

        entry_params = {k: v[0] for k, v in params.items() if k.startswith("entry.")}

        if not entry_params:
            self.stdout.write(self.style.ERROR(
                "\nNo entry.XXXXXXXXX parameters found in the URL.\n"
                "Make sure you filled in at least one field before clicking 'Get link'.\n"
            ))
            return

        self.stdout.write(f"\nFound {len(entry_params)} pre-fill field(s):\n")
        for key, val in entry_params.items():
            self.stdout.write(f"  {key} = '{val}'")

        # Ask user to identify which field is the Event ID
        event_id_field = ""
        event_name_field = ""

        if len(entry_params) == 1:
            event_id_field = list(entry_params.keys())[0]
            self.stdout.write(self.style.SUCCESS(f"\n→ Using {event_id_field} as the Event ID field.\n"))
        else:
            self.stdout.write(
                "\nWhich field should be used as the Event ID (event title will be pre-filled here)?\n"
            )
            for i, (k, v) in enumerate(entry_params.items(), 1):
                self.stdout.write(f"  [{i}] {k}  (had value: '{v}')")
            choice = input("Enter number: ").strip()
            try:
                event_id_field = list(entry_params.keys())[int(choice) - 1]
            except (ValueError, IndexError):
                self.stdout.write(self.style.ERROR("Invalid choice. Aborting.\n"))
                return

            remaining = {k: v for k, v in entry_params.items() if k != event_id_field}
            if remaining:
                self.stdout.write("\nSet an Event Name field? (optional — press Enter to skip)\n")
                for i, (k, v) in enumerate(remaining.items(), 1):
                    self.stdout.write(f"  [{i}] {k}  (had value: '{v}')")
                self.stdout.write("  [0] Skip")
                choice2 = input("Enter number: ").strip()
                if choice2 and choice2 != "0":
                    try:
                        event_name_field = list(remaining.keys())[int(choice2) - 1]
                    except (ValueError, IndexError):
                        pass

        # Write to .env
        env_path = Path(settings.BASE_DIR) / ".env"
        self._update_env(env_path, "GOOGLE_FORM_BASE_URL", base_url)
        self._update_env(env_path, "GOOGLE_FORM_EVENT_ID_FIELD", event_id_field)
        self._update_env(env_path, "GOOGLE_FORM_EVENT_NAME_FIELD", event_name_field)

        self.stdout.write(self.style.SUCCESS(f"\n✓ Updated .env:"))
        self.stdout.write(f"  GOOGLE_FORM_BASE_URL={base_url}")
        self.stdout.write(f"  GOOGLE_FORM_EVENT_ID_FIELD={event_id_field}")
        self.stdout.write(f"  GOOGLE_FORM_EVENT_NAME_FIELD={event_name_field}\n")

        # Reload settings in this process
        settings.GOOGLE_FORM_BASE_URL = base_url
        settings.GOOGLE_FORM_EVENT_ID_FIELD = event_id_field
        settings.GOOGLE_FORM_EVENT_NAME_FIELD = event_name_field

        # Regenerate all QR codes
        self.stdout.write("Regenerating QR codes for all events...\n")
        from events.models import Event, build_form_url
        count = 0
        for event in Event.objects.all():
            try:
                new_url = build_form_url(event)
                if new_url:
                    event.google_form_url = new_url
                event.regenerate_qr()
                if event.qr_code:
                    Event.objects.filter(pk=event.pk).update(
                        qr_code=event.qr_code.name,
                        google_form_url=event.google_form_url,
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ {event.title}"))
                    self.stdout.write(f"    Form URL: {event.google_form_url or 'N/A'}")
                    count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"  ⚠ {event.title} — qrcode not installed"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {event.title}: {e}"))

        self.stdout.write(f"\n✓ {count} QR code(s) regenerated.\n")
        self.stdout.write(self.style.WARNING(
            "⚠ Restart your Django server to load the new .env values.\n"
        ))

    def _update_env(self, env_path, key, value):
        """Update or add a key=value line in the .env file."""
        if not env_path.exists():
            env_path.write_text(f"{key}={value}\n", encoding="utf-8")
            return

        lines = env_path.read_text(encoding="utf-8").splitlines()
        updated = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped == key:
                new_lines.append(f"{key}={value}")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(f"{key}={value}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
