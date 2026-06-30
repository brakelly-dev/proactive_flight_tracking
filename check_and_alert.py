"""
check_and_alert.py
Runs on a schedule (via GitHub Actions) independent of the dashboard.
Checks all tracked flights, and emails the alert group when a flight
newly becomes SEVERE_DELAY or CANCELLED (de-duplicated using a state
file committed back to the repo, so the same alert isn't sent twice).
"""
 
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path
 
import pandas as pd
import requests
 
from flight_status import fetch_arrivals, classify_flight
 
STATE_FILE = Path("data/alert_state.json")
ROSTER_FILE = Path("data/flights_staff.csv")
JAMBOREE_DATES = ["2026-07-18", "2026-07-19"]
AIRPORTS = ["CLT", "CHS"]
 
ALERT_RECIPIENTS = [
    e.strip()
    for e in os.environ.get("ALERT_EMAIL_RECIPIENTS", "").split(",")
    if e.strip()
]
 
# Free SMS option: carrier email-to-SMS gateways, e.g. "5551234567@vtext.com"
# (Verizon), "@txt.att.net" (AT&T), "@tmomail.net" (T-Mobile). Put the full
# gateway addresses here, comma-separated. Sent via the same Gmail account.
SMS_GATEWAY_RECIPIENTS = [
    e.strip()
    for e in os.environ.get("SMS_GATEWAY_RECIPIENTS", "").split(",")
    if e.strip()
]
 
# Free Slack alert: an Incoming Webhook URL from a Slack app (see README).
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
 
 
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}
 
 
def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
 
 
def _smtp_send(to_addresses, subject, body):
    sender = os.environ["GMAIL_SENDER_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
 
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_addresses)
 
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, to_addresses, msg.as_string())
 
 
def send_email(subject, body):
    if not ALERT_RECIPIENTS:
        print("No ALERT_EMAIL_RECIPIENTS configured, skipping email.")
        return
    _smtp_send(ALERT_RECIPIENTS, subject, body)
    print(f"Alert email sent to {ALERT_RECIPIENTS}")
 
 
def send_sms(short_body):
    """SMS gateways generally want a short, plain body and ignore the subject."""
    if not SMS_GATEWAY_RECIPIENTS:
        print("No SMS_GATEWAY_RECIPIENTS configured, skipping SMS.")
        return
    _smtp_send(SMS_GATEWAY_RECIPIENTS, subject="", body=short_body)
    print(f"Alert SMS sent to {SMS_GATEWAY_RECIPIENTS}")
 
 
def send_slack(text):
    if not SLACK_WEBHOOK_URL:
        print("No SLACK_WEBHOOK_URL configured, skipping Slack.")
        return
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
        resp.raise_for_status()
        print("Alert posted to Slack.")
    except Exception as e:
        print(f"WARN: Slack post failed: {e}", file=sys.stderr)
 
 
def main():
    roster = pd.read_csv(ROSTER_FILE, dtype=str)
    state = load_state()
    new_alerts = []
 
    for date_str in JAMBOREE_DATES:
        for airport in AIRPORTS:
            windows = [
                (f"{date_str}T00:00", f"{date_str}T11:59"),
                (f"{date_str}T12:00", f"{date_str}T23:59"),
            ]
            arrivals = []
            for start, end in windows:
                try:
                    arrivals.extend(fetch_arrivals(airport, start, end))
                except Exception as e:
                    print(f"WARN: fetch failed for {airport} {start}-{end}: {e}", file=sys.stderr)
 
            for arrival in arrivals:
                info = classify_flight(arrival)
                flight_no = info["flight_number"]
 
                # only care about flights we're actually tracking
                tracked_rows = roster[roster["flight_number"] == flight_no]
                if tracked_rows.empty:
                    continue
 
                if info["severity"] not in ("CANCELLED", "SEVERE_DELAY"):
                    continue
 
                state_key = f"{flight_no}_{date_str}"
                if state.get(state_key) == info["severity"]:
                    continue  # already alerted on this exact status
 
                state[state_key] = info["severity"]
                for _, staff_row in tracked_rows.iterrows():
                    new_alerts.append(
                        {
                            "flight_number": flight_no,
                            "airport": airport,
                            "date": date_str,
                            "severity": info["severity"],
                            "delay_minutes": info["delay_minutes"],
                            "staff_name": staff_row["staff_name"],
                        }
                    )
 
    if new_alerts:
        lines = ["The following jamboree flights need attention:\n"]
        for a in new_alerts:
            label = "CANCELLED" if a["severity"] == "CANCELLED" else f"DELAYED {a['delay_minutes']} min"
            lines.append(
                f"- {a['flight_number']} into {a['airport']} on {a['date']}: "
                f"{label} (staff: {a['staff_name']})"
            )
        body = "\n".join(lines)
 
        # Short version for SMS (carrier gateways often truncate ~140-160 chars)
        sms_lines = []
        for a in new_alerts:
            status_text = "CANCELLED" if a["severity"] == "CANCELLED" else f"DELAYED {a['delay_minutes']}m"
            sms_lines.append(f"{a['flight_number']} {a['airport']}: {status_text}")
        sms_body = "Jamboree flight alert: " + " | ".join(sms_lines)
        sms_body = sms_body[:300]  # keep it short
 
        send_email(
            subject=f"⚠️ Jamboree flight alert ({len(new_alerts)} update(s))",
            body=body,
        )
        send_sms(sms_body)
        send_slack(f"⚠️ *Jamboree flight alert*\n{body}")
 
        save_state(state)
    else:
        print("No new severe delays or cancellations.")
 
 
if __name__ == "__main__":
    main()
 