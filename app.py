"""
app.py
Jamboree Flight Tracker - Streamlit dashboard.
 
Tracks arrivals into CLT and CHS on the jamboree dates and flags which
staff members are on flights that are severely delayed or cancelled.
 
Run locally:    streamlit run app.py
Deploy:         push to GitHub, then deploy via share.streamlit.io
"""
 
import os
import pandas as pd
import streamlit as st
from datetime import datetime
 
from flight_status import fetch_arrivals, classify_flight
 
st.set_page_config(
    page_title="Jamboree Flight Tracker",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
 
# Streamlit secrets aren't auto-exposed as env vars, so bridge them here
# since flight_status.py reads from os.environ.
if "AERODATABOX_API_KEY" in st.secrets:
    os.environ["AERODATABOX_API_KEY"] = st.secrets["AERODATABOX_API_KEY"]
 
JAMBOREE_DATES = ["2026-07-18", "2026-07-19"]
AIRPORTS = ["CLT", "CHS"]
 
SEVERITY_COLOR = {
    "CANCELLED": "#e63946",
    "SEVERE_DELAY": "#f4a261",
    "MINOR_DELAY": "#e9c46a",
    "ON_TIME": "#2a9d8f",
}
SEVERITY_LABEL = {
    "CANCELLED": "🔴 Cancelled",
    "SEVERE_DELAY": "🟠 Severely Delayed",
    "MINOR_DELAY": "🟡 Minor Delay",
    "ON_TIME": "🟢 On Time",
}
 
 
@st.cache_data(ttl=300)  # refresh underlying data at most every 5 minutes
def load_arrivals_for_date(airport_code, date_str):
    """Pull arrivals in two 12-hour windows (free-tier API limit)."""
    windows = [
        (f"{date_str}T00:00", f"{date_str}T11:59"),
        (f"{date_str}T12:00", f"{date_str}T23:59"),
    ]
    all_arrivals = []
    for start, end in windows:
        try:
            all_arrivals.extend(fetch_arrivals(airport_code, start, end))
        except Exception as e:
            st.warning(f"Could not fetch {airport_code} {start}-{end}: {e}")
    return all_arrivals
 
 
@st.cache_data(ttl=300)
def load_staff_roster():
    return pd.read_csv("data/flights_staff.csv", dtype=str)
 
 
def main():
    st.title("✈️ Jamboree Flight Tracker")
    st.caption(
        "Live arrivals into Charlotte (CLT) and Charleston (CHS) — "
        "July 18–19, 2026"
    )
 
    roster = load_staff_roster()
 
    refresh = st.button("🔄 Refresh now")
    if refresh:
        st.cache_data.clear()
 
    rows = []
    for date_str in JAMBOREE_DATES:
        for airport in AIRPORTS:
            arrivals = load_arrivals_for_date(airport, date_str)
            for arrival in arrivals:
                info = classify_flight(arrival)
                rows.append({**info, "airport": airport, "date": date_str})
 
    if not rows:
        st.info(
            "No flight data loaded yet. Make sure AERODATABOX_API_KEY is "
            "set in Streamlit secrets."
        )
        return
 
    flights_df = pd.DataFrame(rows)
 
    # join staff roster on flight number to find who's impacted
    merged = roster.merge(
        flights_df, on="flight_number", how="left", suffixes=("", "_live")
    )
 
    # --- Top-line summary (2x2 grid stacks cleanly on phones) ---
    row1 = st.columns(2)
    row2 = st.columns(2)
    row1[0].metric("Tracked flights", len(roster["flight_number"].unique()))
    row1[1].metric("Cancelled", int((flights_df["severity"] == "CANCELLED").sum()))
    row2[0].metric("Severely delayed", int((flights_df["severity"] == "SEVERE_DELAY").sum()))
    row2[1].metric("On time", int((flights_df["severity"] == "ON_TIME").sum()))
 
    st.divider()
 
    # --- Impacted staff callout ---
    impacted = merged[merged["severity"].isin(["CANCELLED", "SEVERE_DELAY"])]
    if not impacted.empty:
        st.subheader("🚨 Staff potentially impacted")
        # Card layout instead of a wide table: avoids horizontal scrolling
        # on phones, where a multi-column dataframe is hard to read.
        for _, row in impacted.iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['staff_name']}** — {row['staff_email']}")
                badge = SEVERITY_LABEL.get(row["severity"], row["severity"])
                st.markdown(
                    f"{badge}  ·  Flight **{row['flight_number']}** into **{row['airport']}**"
                )
                detail_cols = st.columns(2)
                if row["severity"] == "CANCELLED":
                    detail_cols[0].caption(f"Scheduled: {row.get('scheduled_local', 'n/a')}")
                else:
                    detail_cols[0].caption(f"Delay: {row.get('delay_minutes', 0)} min")
                    detail_cols[1].caption(f"New time: {row.get('revised_local', 'n/a')}")
    else:
        st.success("No tracked staff currently on a cancelled or severely delayed flight.")
 
    st.divider()
 
    # --- Full flight table ---
    # Collapsed by default on mobile to keep the impacted-staff cards as the
    # main focus; full detail still one tap away.
    display_df = merged.copy()
    display_df["status"] = display_df["severity"].map(SEVERITY_LABEL).fillna("⚪ No data yet")
    with st.expander(f"📋 All tracked flights ({len(merged)})", expanded=False):
        st.dataframe(
            display_df[
                ["flight_number", "airport", "staff_name", "status", "delay_minutes"]
            ].sort_values(["airport", "flight_number"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Tip: rotate your phone to landscape for the full table if columns feel cramped.")
 
    st.caption(f"Last loaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption(
        "Note: this dashboard reflects data only while someone has it open. "
        "Email/text/Slack alerts are sent independently by a scheduled "
        "GitHub Action — see README.md."
    )
 
 
if __name__ == "__main__":
    main()
 