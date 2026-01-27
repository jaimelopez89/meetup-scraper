#!/usr/bin/env python3
"""
Meetup Event Scraper

Scrapes upcoming events from specified Meetup.com groups and exports them to CSV,
with sales rep assignment via config lookup.
"""

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests


def load_config(config_path: str = "config.json") -> dict:
    """Read config.json and return configuration dictionary."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not config.get("browserless_api_key"):
        raise ValueError("browserless_api_key is required in config.json")

    if not config.get("groups"):
        raise ValueError("At least one group is required in config.json")

    return config


def normalize_url(url: str) -> str:
    """Normalize a Meetup group URL to standard format."""
    # Handle URLs like "meetup.com/group-name/" without protocol
    if url.startswith("meetup.com"):
        url = "https://www." + url
    elif not url.startswith("http"):
        # Handle bare group names or paths
        url = "https://www.meetup.com/" + url.lstrip("/")

    # Ensure trailing slash
    if not url.endswith("/"):
        url += "/"

    # Remove query params and fragments, get base group URL
    # Extract just the group name portion
    match = re.search(r"meetup\.com/([^/?#]+)", url)
    if match:
        group_name = match.group(1)
        return f"https://www.meetup.com/{group_name}/"

    return url


def fetch_page(url: str, api_key: str) -> str:
    """Use Browserless API to render a Meetup page and return the HTML."""
    # Normalize and get events page URL
    base_url = normalize_url(url)
    events_url = urljoin(base_url, "events/")

    print(f"  Fetching: {events_url}")

    response = requests.post(
        "https://chrome.browserless.io/content",
        headers={"Content-Type": "application/json"},
        params={"token": api_key},
        json={
            "url": events_url,
            "gotoOptions": {
                "waitUntil": "domcontentloaded",
                "timeout": 60000,
            },
        },
        timeout=90,
    )

    if response.status_code != 200:
        raise Exception(f"Browserless API error: {response.status_code} - {response.text}")

    return response.text


def parse_events(html: str, group_url: str, sales_rep: str) -> list[dict]:
    """Extract event data from Meetup's __NEXT_DATA__ JSON."""
    events = []

    # Extract __NEXT_DATA__ JSON from HTML
    match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        print("  Warning: Could not find __NEXT_DATA__ in HTML")
        return events

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse __NEXT_DATA__ JSON: {e}")
        return events

    # Get Apollo state which contains all the data
    apollo_state = data.get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {})

    if not apollo_state:
        print("  Warning: No Apollo state found in page data")
        return events

    # Build lookup maps for venues and groups
    venues = {}
    groups = {}

    for key, value in apollo_state.items():
        if key.startswith("Venue:"):
            venues[key] = value
        elif key.startswith("Group:"):
            groups[key] = value

    # Extract group name from the first Group object we find
    group_name = ""
    for group_data in groups.values():
        group_name = group_data.get("name", "")
        break

    # Normalize group URL
    normalized_group_url = normalize_url(group_url).rstrip("/")

    # Find all Event objects
    for key, value in apollo_state.items():
        if not key.startswith("Event:"):
            continue

        if value.get("__typename") != "Event":
            continue

        try:
            event = extract_event_data(value, venues, group_name, normalized_group_url, sales_rep)
            if event:
                events.append(event)
        except Exception as e:
            print(f"  Warning: Could not parse event {key}: {e}")
            continue

    return events


def extract_event_data(event_data: dict, venues: dict, group_name: str, group_url: str, sales_rep: str) -> dict | None:
    """Extract structured event data from a Meetup event JSON object."""
    event = {
        "title": "",
        "date": "",
        "time": "",
        "event_url": "",
        "description": "",
        "venue_name": "",
        "address": "",
        "is_online": False,
        "group_name": group_name,
        "group_url": group_url,
        "sales_rep": sales_rep,
    }

    # Title
    event["title"] = event_data.get("title", "")

    # Event URL
    event["event_url"] = event_data.get("eventUrl", "")

    # Skip if no URL (invalid event)
    if not event["event_url"]:
        return None

    # Date and time from ISO datetime
    date_time = event_data.get("dateTime", "")
    if date_time:
        try:
            # Parse ISO format datetime (e.g., "2026-02-10T16:00:00-03:00")
            dt = datetime.fromisoformat(date_time)
            event["date"] = dt.strftime("%Y-%m-%d")
            event["time"] = dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            pass

    # Description (truncate if too long)
    description = event_data.get("description", "") or ""
    if len(description) > 500:
        event["description"] = description[:500] + "..."
    else:
        event["description"] = description

    # Online status
    event["is_online"] = event_data.get("isOnline", False) or event_data.get("eventType") == "ONLINE"

    # Venue information
    if event["is_online"]:
        event["venue_name"] = "Online"
    else:
        venue_ref = event_data.get("venue")
        if venue_ref and isinstance(venue_ref, dict):
            venue_key = venue_ref.get("__ref", "")
            if venue_key in venues:
                venue_data = venues[venue_key]
                event["venue_name"] = venue_data.get("name", "")

                # Build address
                addr_parts = []
                if venue_data.get("address"):
                    addr_parts.append(venue_data["address"])
                if venue_data.get("city"):
                    addr_parts.append(venue_data["city"])
                if venue_data.get("state"):
                    addr_parts.append(venue_data["state"])
                if venue_data.get("country"):
                    addr_parts.append(venue_data["country"].upper())

                event["address"] = ", ".join(addr_parts)

    return event


def filter_upcoming(events: list[dict]) -> list[dict]:
    """Keep only future events."""
    today = datetime.now().date()
    upcoming = []

    for event in events:
        if not event.get("date"):
            # If no date, include it (better safe than sorry)
            upcoming.append(event)
            continue

        try:
            event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
            if event_date >= today:
                upcoming.append(event)
        except ValueError:
            # If date parsing fails, include the event
            upcoming.append(event)

    return upcoming


def deduplicate_events(events: list[dict]) -> list[dict]:
    """Remove duplicate events based on event_url."""
    seen = set()
    unique = []
    for event in events:
        url = event.get("event_url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(event)
    return unique


def export_csv(events: list[dict], filename: str = "events.csv") -> None:
    """Write events to CSV file."""
    if not events:
        print("No events to export.")
        return

    fieldnames = [
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
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)

    print(f"\nExported {len(events)} events to {filename}")


def main() -> None:
    """Orchestrate the scraping process."""
    print("=" * 60)
    print("Meetup Event Scraper")
    print("=" * 60)

    # Load configuration
    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    api_key = config["browserless_api_key"]
    groups = config["groups"]

    # Deduplicate groups by normalized URL
    seen_urls = set()
    unique_groups = []
    for group in groups:
        normalized = normalize_url(group["url"])
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            unique_groups.append(group)

    if len(unique_groups) < len(groups):
        print(f"\nNote: Removed {len(groups) - len(unique_groups)} duplicate group(s)")

    groups = unique_groups
    print(f"\nProcessing {len(groups)} unique group(s)\n")

    all_events = []

    for i, group in enumerate(groups, 1):
        url = group["url"]
        sales_rep = group.get("sales_rep", "")

        print(f"[{i}/{len(groups)}] Processing: {url}")
        print(f"  Sales Rep: {sales_rep}")

        try:
            html = fetch_page(url, api_key)
            events = parse_events(html, url, sales_rep)
            upcoming = filter_upcoming(events)

            print(f"  Found {len(events)} events, {len(upcoming)} upcoming")
            all_events.extend(upcoming)

        except Exception as e:
            print(f"  Error: {e}")
            continue

    # Deduplicate events (in case same event appears in multiple groups)
    all_events = deduplicate_events(all_events)

    print(f"\n{'=' * 60}")
    print(f"Total unique upcoming events: {len(all_events)}")

    # Sort by date
    all_events.sort(key=lambda x: x.get("date", "9999-99-99"))

    # Export to CSV
    export_csv(all_events)

    print("Done!")


if __name__ == "__main__":
    main()
