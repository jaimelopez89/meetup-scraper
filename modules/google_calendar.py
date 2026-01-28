"""Google Calendar integration for creating events with attendee invites."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GCAL_AVAILABLE = True
except ImportError:
    GCAL_AVAILABLE = False


SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "google_token.json"


def authenticate(credentials_path: str = "google_credentials.json"):
    """
    Authenticate with Google Calendar API using OAuth 2.0.

    First run will open a browser for authentication. Subsequent runs
    will use the saved token.

    Args:
        credentials_path: Path to the OAuth client secrets JSON file

    Returns:
        Google Calendar API service object

    Raises:
        ImportError: If required packages are not installed
        FileNotFoundError: If credentials file doesn't exist
    """
    if not GCAL_AVAILABLE:
        raise ImportError(
            "Required packages not installed. Run:\n"
            "pip install google-api-python-client google-auth-oauthlib"
        )

    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            creds.refresh(Request())
        else:
            # Need new authentication
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {credentials_path}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials"
                )

            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        print(f"Saved authentication token to {TOKEN_FILE}")

    service = build("calendar", "v3", credentials=creds)
    return service


def create_calendar_event(
    service,
    event: dict,
    calendar_id: str,
    rep_email: Optional[str],
    default_duration_hours: int = 2,
    send_invites: bool = True
) -> Optional[str]:
    """
    Create a single event in Google Calendar.

    Args:
        service: Google Calendar API service object
        event: Event dictionary from scraper
        calendar_id: Google Calendar ID (use "primary" for main calendar)
        rep_email: Email address for the sales rep (will be added as attendee)
        default_duration_hours: Default event duration
        send_invites: Whether to send email invites to attendees

    Returns:
        Created event ID, or None if creation failed
    """
    title = event.get("title", "Meetup Event")
    date_str = event.get("date", "")
    time_str = event.get("time", "")
    url = event.get("event_url", "")
    description = event.get("description", "")
    venue = event.get("venue_name", "")
    address = event.get("address", "")
    is_online = event.get("is_online", False)
    group_name = event.get("group_name", "")
    sales_rep = event.get("sales_rep", "")

    if not date_str:
        return None

    # Parse date and time
    try:
        if time_str:
            dt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            dt_start = datetime.strptime(date_str, "%Y-%m-%d")
            dt_start = dt_start.replace(hour=18, minute=0)
    except ValueError:
        return None

    dt_end = dt_start + timedelta(hours=default_duration_hours)

    # Build location
    if is_online:
        location = "Online"
    elif address:
        location = address
    elif venue:
        location = venue
    else:
        location = ""

    # Build description
    full_description = (
        f"Sales Rep: {sales_rep}\n"
        f"Group: {group_name}\n\n"
        f"{description}\n\n"
        f"Event URL: {url}"
    )

    # Build event body
    event_body = {
        "summary": title,
        "location": location,
        "description": full_description,
        "start": {
            "dateTime": dt_start.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": dt_end.isoformat(),
            "timeZone": "UTC",
        },
        "source": {
            "title": group_name,
            "url": url,
        },
    }

    # Add sales rep as attendee
    if rep_email:
        event_body["attendees"] = [
            {"email": rep_email, "displayName": sales_rep}
        ]

    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            sendUpdates="all" if send_invites else "none"
        ).execute()

        return created_event.get("id")

    except HttpError as e:
        print(f"    Error creating event: {e}")
        return None


def sync_to_google_calendar(
    events: dict[str, dict],
    rep_emails: dict[str, str],
    config: dict
) -> list[str]:
    """
    Sync events to Google Calendar.

    Only syncs UPCOMING events that haven't been synced yet.
    Adds sales reps as attendees so they receive invites.

    Args:
        events: Dictionary of events keyed by event_url
        rep_emails: Mapping of sales rep names to email addresses
        config: Google Calendar configuration containing:
            - calendar_id: Target calendar ID (default: "primary")
            - credentials_path: Path to OAuth client secrets JSON
            - default_duration_hours: Event duration (default: 2)
            - send_invites: Whether to send email invites (default: True)

    Returns:
        List of event URLs that were synced
    """
    if not GCAL_AVAILABLE:
        print(
            "Warning: Required packages not installed. Run:\n"
            "pip install google-api-python-client google-auth-oauthlib"
        )
        return []

    calendar_id = config.get("calendar_id", "primary")
    credentials_path = config.get("credentials_path", "google_credentials.json")
    default_duration = config.get("default_duration_hours", 2)
    send_invites = config.get("send_invites", True)

    # Filter to UPCOMING events not yet synced
    to_sync = [
        (url, e) for url, e in events.items()
        if e.get("status", "UPCOMING") == "UPCOMING"
        and str(e.get("gcal_synced", "")).lower() != "true"
    ]

    if not to_sync:
        print("No new events to sync to Google Calendar.")
        return []

    try:
        service = authenticate(credentials_path)
    except (ImportError, FileNotFoundError) as e:
        print(f"Error: {e}")
        return []

    synced_urls = []
    print(f"Syncing {len(to_sync)} events to Google Calendar...")

    for url, event in to_sync:
        sales_rep = event.get("sales_rep", "")
        rep_email = rep_emails.get(sales_rep)

        title = event.get("title", "Unknown")[:50]

        if not rep_email:
            print(f"  Skipping '{title}' - no email for rep '{sales_rep}'")
            continue

        event_id = create_calendar_event(
            service,
            event,
            calendar_id,
            rep_email,
            default_duration_hours=default_duration,
            send_invites=send_invites
        )

        if event_id:
            synced_urls.append(url)
            invite_status = "invite sent" if send_invites else "no invite"
            print(f"  Created: {title}... ({rep_email}, {invite_status})")

    print(f"Synced {len(synced_urls)} events to Google Calendar")
    return synced_urls
