"""
Management command: python manage.py show_ngrok_url

Finds your current ngrok public URL by querying the ngrok local API,
then prints:
  - The public HTTPS URL to paste into .env as DJANGO_SITE_BASE_URL
  - The updated Apps Script snippet with the URL already filled in
  - A reminder to regenerate QR codes after updating .env

Usage:
    python manage.py show_ngrok_url
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Find your current ngrok public URL and print setup instructions"

    def handle(self, *args, **options):
        url = self._get_ngrok_url()

        if not url:
            self.stdout.write(self.style.ERROR(
                "\nCould not find a running ngrok tunnel.\n"
                "Make sure ngrok is running:  ngrok http 8000\n"
                "Then run this command again.\n"
            ))
            return

        self.stdout.write(self.style.SUCCESS(f"\n✅  Your ngrok URL is:\n"))
        self.stdout.write(self.style.HTTP_INFO(f"    {url}\n"))

        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.WARNING(
            "\nStep 1 — Update your .env file:\n"
        ))
        self.stdout.write(f"    DJANGO_SITE_BASE_URL={url}\n")
        self.stdout.write(f"    DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,.ngrok-free.app\n")

        self.stdout.write(self.style.WARNING(
            "\nStep 2 — Paste this into your Google Apps Script:\n"
        ))
        self.stdout.write(
            f'    const PORTAL_BASE_URL = "{url}";\n'
            f"\n"
            f"    function onFormSubmit(e) {{\n"
            f'      const values = e.namedValues;\n'
            f'      // Use event title value from the "Event ID" field in your form\n'
            f'      const eventTitle = values["Event ID"] ? values["Event ID"][0] : "";\n'
            f'      const payload = {{ event_id: eventTitle }};\n'
            f'      try {{\n'
            f'        const response = UrlFetchApp.fetch(\n'
            f'          PORTAL_BASE_URL + "/events/form-response/",\n'
            f'          {{\n'
            f'            method: "post",\n'
            f'            contentType: "application/json",\n'
            f'            payload: JSON.stringify(payload),\n'
            f'            muteHttpExceptions: true\n'
            f'          }}\n'
            f'        );\n'
            f'        Logger.log("Status: " + response.getResponseCode());\n'
            f'        Logger.log("Response: " + response.getContentText());\n'
            f'      }} catch (error) {{\n'
            f'        Logger.log("Webhook failed: " + error.toString());\n'
            f'      }}\n'
            f'    }}\n'
        )

        self.stdout.write(self.style.WARNING(
            "\nStep 3 — Regenerate all QR codes so they use the new URL:\n"
        ))
        self.stdout.write(
            "    Go to each event in the portal → click 'Regenerate QR Code'\n"
            "    OR run: python manage.py regenerate_all_qr\n"
        )
        self.stdout.write("─" * 60 + "\n")

    def _get_ngrok_url(self):
        """Query the ngrok local API (http://127.0.0.1:4040/api/tunnels)."""
        import urllib.request
        import json

        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:4040/api/tunnels", timeout=3
            ) as resp:
                data = json.loads(resp.read())
                tunnels = data.get("tunnels", [])
                # Prefer the HTTPS tunnel
                for tunnel in tunnels:
                    public_url = tunnel.get("public_url", "")
                    if public_url.startswith("https://"):
                        return public_url
                # Fall back to any tunnel
                for tunnel in tunnels:
                    public_url = tunnel.get("public_url", "")
                    if public_url:
                        return public_url
        except Exception:
            pass
        return None
