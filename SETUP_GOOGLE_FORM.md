# 🔗 Setting Up the Google Form for QR Code Registration

---

## How the QR Code Flow Works

```
Attendee scans QR code (phone camera)
         ↓
Portal /events/qr/<uuid>/ is hit:
  → Counter increments immediately (+1)
  → Anonymous record saved to DB
  → Redirects to pre-filled Google Form
         ↓
Attendee fills: Name, Email, Phone → submits form
         ↓
(Optional) Apps Script webhook fires:
  → Sends name/email/phone to portal
  → Portal enriches the anonymous record (no double count)
  → Reports now show full details
```

**The live count works immediately on QR scan — no public server needed for that.**
The Apps Script webhook is optional and only adds names to reports.

---

## Step 1 — Create the Google Form

1. Open [forms.google.com](https://forms.google.com) and sign in.
2. Click **Blank form**.
3. Set the title, e.g. **"Swahilipot Hub Event Registration"**.
4. Add these questions:

| Question | Type | Notes |
|---|---|---|
| Event ID | Short answer | **Required** — pre-filled by QR code |
| Event Name | Short answer | Optional — pre-filled by QR code |
| Full Name | Short answer | Required |
| Email Address | Short answer | Required |
| Phone Number | Short answer | Required |

5. Click **Send** → copy the **sharing link** (the `/viewform` URL).

---

## Step 2 — Find the pre-fill entry IDs

1. In your form editor, click **⋮ (three dots)** → **"Get pre-filled link"**.
2. Type a sample answer in the **Event ID** field (e.g. "1") and in **Event Name** (e.g. "Test").
3. Click **Get link** → copy the URL.
   Example:
   ```
   https://docs.google.com/forms/d/e/1FAIpQLSe.../viewform?usp=pp_url&entry.87039877=1&entry.1265070359=Test
   ```
4. Extract the entry IDs:
   - `entry.87039877` → Event ID field
   - `entry.1265070359` → Event Name field

---

## Step 3 — Update your `.env` file

Open `swahilipot_portal/.env` and set:

```env
GOOGLE_FORM_BASE_URL=https://docs.google.com/forms/d/e/1FAIpQLSe.../viewform
GOOGLE_FORM_EVENT_ID_FIELD=entry.87039877
GOOGLE_FORM_EVENT_NAME_FIELD=entry.1265070359
```

Then run:

```bash
python manage.py refresh_form_urls
```

This rebuilds the pre-filled URLs for all existing events.

---

## Step 4 — Regenerate QR codes (if needed)

If your QR codes were generated before setting the form URL:

```bash
python manage.py regenerate_qr_codes
```

Or from the event detail page, click **Regenerate QR Code** (admins only).

---

## Step 5 — Apps Script webhook (optional — adds names to reports)

### Why you need this
Without the webhook, reports show `(QR Scan)` instead of names.
With it, reports show the real name/email/phone from the Google Form.

### Setup

1. In your Google Form, click **Responses** → green Sheets icon → create a linked Sheet.
2. In the Sheet: **Extensions** → **Apps Script**.
3. Paste the contents of `google_apps_script.js` (in the portal folder).
4. Set `PORTAL_BASE_URL` to your portal's public URL (see below for options).
5. **Triggers** (clock icon) → **Add Trigger**:
   - Function: `onFormSubmit`
   - Event source: From spreadsheet
   - Event type: On form submit
6. Authorise when prompted.

---

## 🌐 Making Your Portal Publicly Accessible (for QR Scans from Phones)

The QR code encodes your portal URL. For phones to scan it and reach your portal,
the portal must be reachable from the phone. Here are your options:

---

### Option A — Cloudflare Tunnel (FREE, permanent, recommended)

**Best choice: works even when your host PC is off (if you deploy to a server)**

**If running on your own PC (must be on):**

1. Download `cloudflared` from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
   - Windows: download `cloudflared-windows-amd64.exe`, rename to `cloudflared.exe`
   
2. Start your Django server normally:
   ```cmd
   python manage.py runserver
   ```

3. In a second terminal, start the tunnel:
   ```cmd
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

4. You get a URL like `https://random-name.trycloudflare.com` — this is permanent
   for as long as the process runs, and **free with no account needed**.

5. Update your `.env`:
   ```env
   DJANGO_SITE_BASE_URL=https://random-name.trycloudflare.com
   DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,random-name.trycloudflare.com
   ```

6. Set the same URL in `google_apps_script.js` as `PORTAL_BASE_URL`.

7. Run `python manage.py regenerate_qr_codes` to rebuild QR codes.

> **⚠️ The URL changes every time you restart cloudflared** (on the free anonymous tier).
> For a permanent URL, create a free Cloudflare account and use named tunnels:
> https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/

---

### Option B — ngrok (free tier, URL changes on restart)

1. Download from https://ngrok.com/download
2. Sign up for a free account, get your auth token.
3. Run:
   ```cmd
   ngrok http 8000
   ```
4. Copy the `https://abc123.ngrok-free.app` URL.
5. Update `.env` as above, regenerate QR codes.

> **ngrok free tier limitation**: URL changes every time you restart ngrok.
> To get a fixed URL on ngrok, you need a paid plan (~$10/month).

---

### Option C — Deploy to a real server (recommended for production)

For 24/7 availability without leaving your PC on:

**Free hosting options:**
- **Railway** (https://railway.app) — free tier, supports Django + PostgreSQL
- **Render** (https://render.com) — free tier, auto-deploy from GitHub
- **PythonAnywhere** (https://www.pythonanywhere.com) — free tier for Django

**Basic deployment steps for Railway:**
1. Push the `swahilipot_portal/` folder to a GitHub repository.
2. Sign up at railway.app → New Project → Deploy from GitHub.
3. Add a PostgreSQL plugin.
4. Set environment variables (copy from `.env`).
5. Your portal gets a permanent URL like `https://swahilipot.up.railway.app`.
6. Update `DJANGO_SITE_BASE_URL` and regenerate QR codes.

See `DEPLOY.md` for a complete deployment guide.

---

### Option D — Local network only (no internet access needed)

If the event is indoors on the same WiFi network:

1. Find your computer's local IP:
   ```cmd
   ipconfig
   ```
   Look for `IPv4 Address` e.g. `192.168.1.100`

2. Update `.env`:
   ```env
   DJANGO_SITE_BASE_URL=http://192.168.1.100:8000
   DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.100
   ```

3. Run Django on all interfaces:
   ```cmd
   python manage.py runserver 0.0.0.0:8000
   ```

4. Regenerate QR codes. Phones on the same WiFi can scan them.

> **Limitation**: Only works on the same WiFi network.
> The Apps Script webhook will NOT work with this option (Google can't reach local IPs).

---

## Summary: Which option should I use?

| Situation | Recommended |
|---|---|
| One-time indoor event, same WiFi | Option D (local network) |
| Events where phones have mobile data | Option A (Cloudflare Tunnel) |
| Regular events, want names in reports | Option A + Apps Script |
| Production portal, multiple events | Option C (deploy to server) |
| 24/7 access without leaving PC on | Option C (cloud deployment) |
