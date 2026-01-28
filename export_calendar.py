#!/usr/bin/env python3
"""
Export upcoming events to a combined ICS file for Google Calendar import.

Only exports events that:
- Have status UPCOMING (not DONE)
- Haven't been exported before (calendar_exported != True)

After export, marks the events as exported in events.csv.
"""

from modules.csv_manager import (
    load_existing_events,
    update_event_statuses,
    save_events,
    mark_calendar_exported,
)
from modules.calendar_generator import generate_combined_ics


def main():
    print("=" * 60)
    print("Calendar Export")
    print("=" * 60)

    # Load and update events
    print("\nLoading events...")
    events = load_existing_events("events.csv")
    events = update_event_statuses(events)

    total = len(events)
    upcoming = sum(1 for e in events.values() if e.get("status") == "UPCOMING")
    already_exported = sum(
        1 for e in events.values()
        if e.get("status") == "UPCOMING" and str(e.get("calendar_exported", "")).lower() == "true"
    )

    print(f"Total events: {total}")
    print(f"Upcoming events: {upcoming}")
    print(f"Already exported: {already_exported}")
    print(f"To export: {upcoming - already_exported}")

    # Generate combined ICS
    print("\nGenerating calendar file...")
    filepath, exported_urls = generate_combined_ics(events, "calendars/all_events.ics")

    if filepath and exported_urls:
        # Mark as exported and save
        events = mark_calendar_exported(events, exported_urls)
        save_events(events, "events.csv")
        print(f"\nSuccess! Import this file into Google Calendar:")
        print(f"  {filepath}")
    elif not exported_urls:
        print("\nNo new events to export.")

    print("\nDone!")


if __name__ == "__main__":
    main()
