# Jamboree Flight Tracker

Tracks arrivals into **Charlotte (CLT)** and **Charleston (CHS)** on
**July 18–19, 2026**, flags delays/cancellations, shows which staff are
impacted, and automatically alerts a group by **email, text, and/or Slack**
when something goes wrong.

## How it works

- **`app.py`** — Streamlit dashboard, public link, viewable by anyone.
- **`check_and_alert.py`** — runs independently every 30 minutes via GitHub
  Actions (`.github/workflows/check_flights.yml`), so alerts fire even if
  nobody has the dashboard open.
- **`data/flights_staff.csv`** — your roster: which staff are on which
  flights. **Edit this before the event.**
- **`data/alert_state.json`** — auto-generated; prevents duplicate alerts
  for a status that hasn't changed.

All three alert channels are optional and independent — set up whichever
ones you want; any you skip are just silently no-op'd.

---

## Part 1 — Setup

### 1.1 Get an AeroDataBox API key (free)
1. Go to https://rapidapi.com/aedbx-aedbx/api/aerodatabox and create a free RapidAPI account.
2. Subscribe to the free/basic plan.
3. Copy your RapidAPI key.
4. In the RapidAPI playground, run one test query against `KCLT` and confirm the response field names (`status`, `arrival.scheduledTimeLocal`, etc.) match what's used in `flight_status.py` — verify this once, since the schema can shift.

### 1.2 Set up email alerts (Gmail, free)
1. Use an existing Gmail account, or create one just for this.
2. Turn on 2-Step Verification: https://myaccount.google.com/security
3. Create an App Password: https://myaccount.google.com/apppasswords → "Mail" → copy the 16-character password.

### 1.3 Set up text alerts (free, via carrier email-to-SMS gateway)
No paid SMS service needed — every major US carrier lets you text a phone
by emailing a special address. Build each recipient's address as
`<10-digit-number>@<carrier-gateway>`:

| Carrier | Gateway |
|---|---|
| AT&T | `@txt.att.net` |
| Verizon | `@vtext.com` |
| T-Mobile | `@tmomail.net` |
| Sprint (T-Mobile merged, may still work) | `@messaging.sprintpcs.com` |
| Google Fi | `@msg.fi.google.com` |

Example: a Verizon number `555-123-4567` → `5551234567@vtext.com`.

**Caveats:** deliverability isn't guaranteed (carriers sometimes filter
gateway email as spam), and there can be a short delay. Test this with
each real recipient's phone before the event. If anyone's carrier isn't
listed or gateway texts don't arrive reliably for them, email/Slack are
the fallback for that person.

### 1.4 Set up Slack alerts (free)
1. Go to https://api.slack.com/apps → **Create New App** → "From scratch".
2. Name it (e.g. "Jamboree Flight Alerts") and pick your workspace.
3. In the app settings, go to **Incoming Webhooks** → toggle it on → **Add New Webhook to Workspace** → choose the channel for alerts.
4. Copy the generated webhook URL (looks like `https://hooks.slack.com/services/...`).

### 1.5 Fill in your flight/staff roster
Edit `data/flights_staff.csv`. One row per staff member per flight.

Columns: `flight_number`, `airline_iata`, `origin_iata`, `destination_iata`,
`arrival_date` (`2026-07-18` or `2026-07-19`), `scheduled_arrival_local`,
`staff_name`, `staff_email`.

### 1.6 Push this repo to your GitHub
```
git init
git add .
git commit -m "Initial jamboree flight tracker"
git remote add origin https://github.com/YOUR-USERNAME/jamboree-flight-tracker.git
git push -u origin main
```

### 1.7 Add GitHub Actions secrets
In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Secret name | Value | Required? |
|---|---|---|
| `AERODATABOX_API_KEY` | from step 1.1 | Yes |
| `GMAIL_SENDER_ADDRESS` | Gmail address from step 1.2 | Yes, if using email or SMS |
| `GMAIL_APP_PASSWORD` | 16-char app password from step 1.2 | Yes, if using email or SMS |
| `ALERT_EMAIL_RECIPIENTS` | comma-separated emails, e.g. `lead1@org.com,lead2@org.com` | If using email |
| `SMS_GATEWAY_RECIPIENTS` | comma-separated gateway addresses, e.g. `5551234567@vtext.com,5559876543@txt.att.net` | If using SMS |
| `SLACK_WEBHOOK_URL` | from step 1.4 | If using Slack |

### 1.8 Set up the dashboard's own secret (separate from GitHub Actions)
The Streamlit app only needs the AeroDataBox key — you'll paste this directly into Streamlit Community Cloud in Part 3, not as a GitHub secret.

---

## Part 2 — Testing (do this before the event)

1. **Test the alert script locally**, with real flights happening right now (any date), to confirm all three channels work end-to-end:
   ```
   export AERODATABOX_API_KEY="..."
   export GMAIL_SENDER_ADDRESS="..."
   export GMAIL_APP_PASSWORD="..."
   export ALERT_EMAIL_RECIPIENTS="you@example.com"
   export SMS_GATEWAY_RECIPIENTS="5551234567@vtext.com"
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
   python check_and_alert.py
   ```
   To force a test alert even if nothing's actually delayed, temporarily
   lower `SEVERE_DELAY_MINUTES` in `flight_status.py` (e.g. to `1`) and
   point `JAMBOREE_DATES`/the roster at a real flight arriving soon. Revert
   afterward.

2. **Test the GitHub Actions workflow** without waiting for the schedule: go to your repo's **Actions** tab → "Jamboree Flight Alert Check" → **Run workflow** (this uses the `workflow_dispatch` trigger already in the YAML). Check the run logs to confirm it fetched flights and attempted sends.

3. **Test each text recipient individually** ahead of time — gateway deliverability varies by carrier, so confirm each phone actually receives a message, not just that the script ran without error.

4. **Test the dashboard locally** before deploying:
   ```
   pip install -r requirements.txt
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # edit secrets.toml with your real AeroDataBox key
   streamlit run app.py
   ```

---

## Part 3 — Deploy the dashboard (Streamlit Community Cloud, free)

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **New app** → select this repo → branch `main` → file `app.py`.
3. Before deploying, click **Advanced settings → Secrets** and paste:
   ```
   AERODATABOX_API_KEY = "your-rapidapi-key-here"
   ```
4. Click **Deploy**. You'll get a public URL — share that link with the team. No login required to view it.

---

## Part 4 — Day-of checklist

- Confirm the GitHub Actions schedule is firing (Actions tab shows runs every 30 min during the event window).
- Keep the Streamlit dashboard link handy for anyone who wants the live visual view.
- If you add/change flights or staff mid-event, edit `data/flights_staff.csv` and push — both the dashboard and the next scheduled Action run will pick it up.

## Mobile access
The dashboard works on phones out of the box — Streamlit's public URL is
just a responsive web page, nothing extra to install. The layout is built
to avoid horizontal scrolling on small screens: impacted-staff info shows
as stacked cards instead of a wide table, and the full flight list is
tucked behind a collapsible "All tracked flights" section. No app, login,
or special setup needed on the phone side — just open the link in any
mobile browser.

## Notes / limitations
- AeroDataBox's free tier has request quotas — if exceeded, the dashboard shows a warning instead of crashing, and the alert script logs a warning and continues with whatever data it got.
- Alerts de-dupe by exact status per flight per date, so a flight moving from "severely delayed" to "cancelled" still triggers a new alert (intentional), but won't re-fire every 30 minutes for an unchanged status.
- Gmail's free sending cap (~500/day) is far more than this needs.
- SMS via carrier gateway is free but not guaranteed-delivery — treat it as a bonus channel, not the sole channel, for anything truly critical.
