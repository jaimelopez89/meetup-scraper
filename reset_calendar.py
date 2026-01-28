#!/usr/bin/env python3
"""
Reset Google Calendar events and re-sync with correct timezones.

This script:
1. Finds and deletes calendar events that match our scraped events
2. Resets the gcal_synced flag in events.csv
3. Optionally re-runs the sync to recreate events with correct timezones

Usage:
    python reset_calendar.py           # Delete events and reset tracking
    python reset_calendar.py --resync  # Delete, reset, and immediately resync
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from modules.google_calendar import authenticate, GCAL_AVAILABLE


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_events(filepath: str = "events.csv") -> list[dict]:
    """Load events from CSV."""
    path = Path(filepath)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_events(events: list[dict], filepath: str = "events.csv") -> None:
    """Save events to CSV with gcal_synced reset."""
    if not events:
        return

    fieldnames = list(events[0].keys())

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)


def find_and_delete_events(service, calendar_id: str, events: list[dict]) -> int:
    """
    Find and delete Google Calendar events that match our scraped events.

    Returns the number of events deleted.
    """
    deleted_count = 0

    # Get synced events
    synced_events = [
        e for e in events
        if str(e.get("gcal_synced", "")).lower() == "true"
        and e.get("status", "UPCOMING") == "UPCOMING"
    ]

    if not synced_events:
        print("No synced events to delete.")
        return 0

    print(f"Found {len(synced_events)} synced events to delete...")

    for event in synced_events:
        title = event.get("title", "")
        date_str = event.get("date", "")

        if not title or not date_str:
            continue

        try:
            # Search for events on this date with matching title
            event_date = datetime.strptime(date_str, "%Y-%m-%d")
            time_min = event_date.isoformat() + "Z"
            time_max = (event_date + timedelta(days=1)).isoformat() + "Z"

            results = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                q=title[:50],  # Search by title (first 50 chars)
                singleEvents=True
            ).execute()

            calendar_events = results.get("items", [])

            for cal_event in calendar_events:
                cal_title = cal_event.get("summary", "")
                # Match if titles are similar
                if title.lower() in cal_title.lower() or cal_title.lower() in title.lower():
                    event_id = cal_event.get("id")
                    try:
                        service.events().delete(
                            calendarId=calendar_id,
                            eventId=event_id
                        ).execute()
                        deleted_count += 1
                        print(f"  Deleted: {title[:50]}...")
                    except Exception as e:
                        print(f"  Error deleting '{title[:30]}...': {e}")
                    break

        except Exception as e:
            print(f"  Error searching for '{title[:30]}...': {e}")
            continue

    return deleted_count


def reset_gcal_synced(events: list[dict]) -> list[dict]:
    """Reset gcal_synced flag for all UPCOMING events."""
    reset_count = 0
    for event in events:
        if str(event.get("gcal_synced", "")).lower() == "true":
            event["gcal_synced"] = ""
            reset_count += 1

    print(f"Reset gcal_synced flag for {reset_count} events.")
    return events


def main():
    parser = argparse.ArgumentParser(
        description="Reset Google Calendar events and optionally resync"
    )
    parser.add_argument(
        "--resync",
        action="store_true",
        help="Re-sync events after deleting (runs scraper)"
    )
    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Skip deleting from Google Calendar, only reset CSV"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Google Calendar Reset")
    print("=" * 60)

    # Load config and events
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    events = load_events()
    if not events:
        print("No events found in events.csv")
        sys.exit(1)

    gcal_config = config.get("google_calendar", {})
    calendar_id = gcal_config.get("calendar_id", "primary")
    credentials_path = gcal_config.get("credentials_path", "google_credentials.json")

    # Delete from Google Calendar
    if not args.skip_delete:
        if not GCAL_AVAILABLE:
            print("Google Calendar packages not installed.")
            print("Run: pip install google-api-python-client google-auth-oauthlib")
            sys.exit(1)

        print("\nAuthenticating with Google Calendar...")
        try:
            service = authenticate(credentials_path)
        except Exception as e:
            print(f"Error authenticating: {e}")
            sys.exit(1)

        print(f"\nDeleting events from calendar '{calendar_id}'...")
        deleted = find_and_delete_events(service, calendar_id, events)
        print(f"\nDeleted {deleted} events from Google Calendar.")

    # Reset tracking in CSV
    print("\nResetting event tracking...")
    events = reset_gcal_synced(events)
    save_events(events)
    print("Saved updated events.csv")

    # Optionally resync
    if args.resync:
        print("\n" + "=" * 60)
        print("Re-syncing events...")
        print("=" * 60)
        import subprocess
        subprocess.run([sys.executable, "scraper.py"])
    else:
        print("\nRun 'python scraper.py' to re-sync events with correct timezones.")

    print("\nDone!")


if __name__ == "__main__":
    main()
