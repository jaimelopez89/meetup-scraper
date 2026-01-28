"""CSV state persistence and status tracking for meetup events."""

import csv
from datetime import datetime
from pathlib import Path


FIELDNAMES = [
    "title",
    "date",
    "time",
    "event_url",
    "description",
    "venue_name",
    "address",
    "is_online",
    "group_name",
    "group_url",
    "sales_rep",
    "status",
    "calendar_exported",
]


def load_existing_events(filepath: str = "events.csv") -> dict[str, dict]:
    """
    Load existing events from CSV into a dict keyed by event_url.

    Args:
        filepath: Path to the CSV file

    Returns:
        Dictionary mapping event_url to event data
    """
    path = Path(filepath)
    events = {}

    if not path.exists():
        return events

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("event_url", "")
            if url:
                # Convert is_online string to bool if needed
                if isinstance(row.get("is_online"), str):
                    row["is_online"] = row["is_online"].lower() == "true"
                # Add status if missing (for migration)
                if "status" not in row or not row.get("status"):
                    row["status"] = "UPCOMING"
                events[url] = row

    return events


def update_event_statuses(events: dict[str, dict]) -> dict[str, dict]:
    """
    Update event statuses based on current date.

    Past events are marked as DONE, future events as UPCOMING.

    Args:
        events: Dictionary of events keyed by event_url

    Returns:
        Updated dictionary with correct statuses
    """
    today = datetime.now().date()

    for url, event in events.items():
        date_str = event.get("date", "")
        if not date_str:
            # No date, assume upcoming
            event["status"] = "UPCOMING"
            continue

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if event_date < today:
                event["status"] = "DONE"
            else:
                event["status"] = "UPCOMING"
        except ValueError:
            # Can't parse date, assume upcoming
            event["status"] = "UPCOMING"

    return events


def merge_events(
    existing: dict[str, dict],
    new: list[dict]
) -> tuple[dict[str, dict], list[dict]]:
    """
    Merge new scraped events with existing events.

    Only adds events that don't already exist (by event_url).

    Args:
        existing: Dictionary of existing events keyed by event_url
        new: List of newly scraped events

    Returns:
        Tuple of (all_events dict, list of newly_added events)
    """
    newly_added = []

    for event in new:
        url = event.get("event_url", "")
        if not url:
            continue

        if url not in existing:
            # New event - add status and store
            event["status"] = "UPCOMING"
            existing[url] = event
            newly_added.append(event)

    return existing, newly_added


def save_events(events: dict[str, dict], filepath: str = "events.csv") -> None:
    """
    Save events to CSV file with UTF-8 encoding.

    Args:
        events: Dictionary of events keyed by event_url
        filepath: Path to output CSV file
    """
    if not events:
        print("No events to save.")
        return

    # Convert dict to list and sort by date
    event_list = list(events.values())
    event_list.sort(key=lambda x: x.get("date", "9999-99-99"))

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(event_list)

    print(f"Saved {len(event_list)} events to {filepath}")


def mark_calendar_exported(events: dict[str, dict], exported_urls: list[str]) -> dict[str, dict]:
    """
    Mark events as exported to calendar.

    Args:
        events: Dictionary of events keyed by event_url
        exported_urls: List of event URLs that were exported

    Returns:
        Updated events dictionary
    """
    for url in exported_urls:
        if url in events:
            events[url]["calendar_exported"] = "True"
    return events
