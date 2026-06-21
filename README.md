# Swahilipot Portal

Production-ready Django MVP for attendance, communication, tasks, events, suggestions, dashboards, and reports.

## Quick Start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data
python manage.py runserver
```

Open http://127.0.0.1:8000/.

Python 3.12+ installs Django 6.x, the latest official stable series as of June 2026. Python 3.11 installs Django 5.2 LTS for local compatibility.

## Environment

SQLite is used by default for development. Set `DATABASE_URL` for PostgreSQL production:

```bash
set DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
set DJANGO_SECRET_KEY=change-me
set DJANGO_DEBUG=False
set DJANGO_ALLOWED_HOSTS=example.com,www.example.com
```

## Schema Summary

- `accounts`: custom user with role, department, profile fields.
- `attendance`: project sites, geofenced attendance records, activity logs.
- `communication`: announcements, department channels, channel messages, direct messages, notifications.
- `tasks`: assigned tasks, comments, attachments.
- `events`: events, registrations, QR codes, attendance.
- `suggestions`: suggestion box and admin responses.
- `dashboard`: analytics and downloadable reports.

## Notes

- GPS check-in/out uses the browser Geolocation API and server-side Haversine verification.
- Event QR codes are generated using the `qrcode` package.
- Excel exports use `openpyxl`; PDF exports use `reportlab`.
- Bootstrap 5, Leaflet.js, and Chart.js are loaded from CDNs.
