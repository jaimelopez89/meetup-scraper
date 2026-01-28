"""ICS calendar file generation for meetup events."""

import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from icalendar import Calendar, Event, vText
    ICALENDAR_AVAILABLE = True
except ImportError:
    ICALENDAR_AVAILABLE = False


def sanitize_filename(name: str) -> str:
    """
    Create a safe filename from event title.

    Args:
        name: Original event title

    Returns:
        Sanitized filename string
    """
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    safe = re.sub(r'\s+', '_', safe)
    safe = safe[:50]  # Limit length
    return safe or "event"


def generate_ics(
    event: dict,
    rep_email: Optional[str],
    output_dir: str = "calendars",
    default_duration_hours: int = 2
) -> Optional[str]:
    """
    Generate an ICS file for a single event.

    Args:
        event: Event dictionary
        rep_email: Email address for the sales rep (for calendar invite)
        output_dir: Directory to save ICS files
        default_duration_hours: Default event duration if not specified

    Returns:
        Path to generated file, or None if generation failed
    """
    if not ICALENDAR_AVAILABLE:
        return None

    title = event.get("title", "Meetup Event")
    date_str = event.get("date", "")
    time_str = event.get("time", "")
    url = event.get("event_url", "")
    description = event.get("description", "")
    venue = event.get("venue_name", "")
    address = event.get("address", "")
    is_online = event.get("is_online", False)
    group_name = event.get("group_name", "")

    if not date_str:
        return None

    # Parse date and time
    try:
        if time_str:
            dt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            dt_start = datetime.strptime(date_str, "%Y-%m-%d")
            dt_start = dt_start.replace(hour=18, minute=0)  # Default to 6 PM
    except ValueError:
        return None

    dt_end = dt_start + timedelta(hours=default_duration_hours)

    # Create calendar
    cal = Calendar()
    cal.add("prodid", "-//Meetup Event Scraper//EN")
    cal.add("version", "2.0")
    cal.add("method", "PUBLISH")

    # Create event
    ical_event = Event()
    ical_event.add("summary", title)
    ical_event.add("dtstart", dt_start)
    ical_event.add("dtend", dt_end)

    # Create unique ID based on URL
    uid = hashlib.md5(url.encode()).hexdigest() + "@meetup-scraper"
    ical_event.add("uid", uid)

    ical_event.add("dtstamp", datetime.now())

    # Location
    if is_online:
        ical_event.add("location", "Online")
    elif address:
        ical_event.add("location", address)
    elif venue:
        ical_event.add("location", venue)

    # Description with link
    full_description = f"{description}\n\nEvent URL: {url}\nGroup: {group_name}"
    ical_event.add("description", full_description)

    # URL
    if url:
        ical_event.add("url", url)

    # Add organizer if email provided
    if rep_email:
        ical_event.add("organizer", f"mailto:{rep_email}")

    cal.add_component(ical_event)

    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename
    safe_title = sanitize_filename(title)
    filename = f"{date_str}_{safe_title}.ics"
    filepath = output_path / filename

    # Write file
    with open(filepath, "wb") as f:
        f.write(cal.to_ical())

    return str(filepath)


def generate_all_ics(
    new_events: list[dict],
    rep_emails: dict[str, str],
    config: dict
) -> list[str]:
    """
    Generate ICS files for all new events.

    Args:
        new_events: List of newly discovered events
        rep_emails: Mapping of sales rep names to email addresses
        config: Calendar configuration containing:
            - output_dir: Directory for ICS files (default: "calendars")
            - default_duration_hours: Event duration (default: 2)

    Returns:
        List of generated file paths
    """
    if not ICALENDAR_AVAILABLE:
        print(
            "Warning: icalendar not installed. Skipping calendar generation. "
            "Install with: pip install icalendar"
        )
        return []

    if not new_events:
        return []

    output_dir = config.get("output_dir", "calendars")
    default_duration = config.get("default_duration_hours", 2)

    generated = []

    for event in new_events:
        sales_rep = event.get("sales_rep", "")
        rep_email = rep_emails.get(sales_rep)

        filepath = generate_ics(
            event,
            rep_email,
            output_dir=output_dir,
            default_duration_hours=default_duration
        )

        if filepath:
            generated.append(filepath)

    if generated:
        print(f"Generated {len(generated)} calendar files in {output_dir}/")

    return generated
