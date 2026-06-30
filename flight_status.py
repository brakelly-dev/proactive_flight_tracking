"""
flight_status.py
Shared helpers for pulling arrival status from the AeroDataBox API
(via RapidAPI) and classifying delay/cancellation severity.
 
AeroDataBox docs: https://rapidapi.com/aedbx-aedbx/api/aerodatabox
Endpoint used: Flight Arrivals/Departures By Airport (ICAO), which returns
ALL flights into an airport in a local time window in one call -- this is
why we use it instead of querying one flight number at a time.
"""
 
import os
import requests
from datetime import datetime
 
AERODATABOX_HOST = "aerodatabox.p.rapidapi.com"
 
# Charlotte Douglas Intl = KCLT, Charleston Intl (SC) = KCHS
AIRPORT_ICAO = {
    "CLT": "KCLT",
    "CHS": "KCHS",
}
 
SEVERE_DELAY_MINUTES = 60  # tweak this threshold as needed
 
 
def _headers():
    api_key = os.environ.get("AERODATABOX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "AERODATABOX_API_KEY is not set. Add it to Streamlit secrets "
            "or as a GitHub Actions secret."
        )
    return {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": AERODATABOX_HOST,
    }
 
 
def fetch_arrivals(airport_code, from_local_iso, to_local_iso):
    """
    Fetch all arrivals into an airport between two local datetimes.
    AeroDataBox free tier typically limits each window to 12 hours,
    so callers should split a full day into two windows.
 
    from_local_iso / to_local_iso format: 'YYYY-MM-DDTHH:MM'
    """
    icao = AIRPORT_ICAO[airport_code]
    url = (
        f"https://{AERODATABOX_HOST}/flights/airports/icao/"
        f"{icao}/{from_local_iso}/{to_local_iso}"
    )
    params = {
        "withLeg": "false",
        "direction": "Arrival",
        "withCancelled": "true",
        "withCodeshared": "false",
        "withCargo": "false",
        "withPrivate": "false",
    }
    resp = requests.get(url, headers=_headers(), params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("arrivals", [])
 
 
def classify_flight(arrival):
    """
    Normalize an AeroDataBox arrival record into a simple status dict.
    Field names follow the AeroDataBox schema; verify against a live
    response once you have an API key, as field availability can vary
    by airline/data source.
    """
    number = arrival.get("number", "UNKNOWN")
    status_raw = (arrival.get("status") or "Unknown").lower()
 
    movement = arrival.get("arrival", {})
    scheduled = movement.get("scheduledTimeLocal")
    revised = movement.get("revisedTimeLocal") or movement.get("actualTimeLocal")
 
    delay_minutes = 0
    if scheduled and revised:
        try:
            fmt = "%Y-%m-%d %H:%M%z"
            t_sched = datetime.strptime(scheduled, fmt)
            t_rev = datetime.strptime(revised, fmt)
            delay_minutes = int((t_rev - t_sched).total_seconds() // 60)
        except (ValueError, TypeError):
            delay_minutes = 0
 
    is_cancelled = "cancel" in status_raw
    is_severe_delay = (not is_cancelled) and delay_minutes >= SEVERE_DELAY_MINUTES
 
    if is_cancelled:
        severity = "CANCELLED"
    elif is_severe_delay:
        severity = "SEVERE_DELAY"
    elif delay_minutes > 0:
        severity = "MINOR_DELAY"
    else:
        severity = "ON_TIME"
 
    return {
        "flight_number": number,
        "status_raw": status_raw,
        "scheduled_local": scheduled,
        "revised_local": revised,
        "delay_minutes": delay_minutes,
        "severity": severity,
    }