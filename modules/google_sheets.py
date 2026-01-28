"""Google Sheets integration for pushing event data."""

from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def authenticate(credentials_path: str) -> "gspread.Client":
    """
    Authenticate with Google using a service account.

    Args:
        credentials_path: Path to the Google service account JSON file

    Returns:
        Authenticated gspread client

    Raises:
        ImportError: If gspread is not installed
        FileNotFoundError: If credentials file doesn't exist
    """
    if not GSPREAD_AVAILABLE:
        raise ImportError(
            "gspread and google-auth are required for Google Sheets integration. "
            "Install them with: pip install gspread google-auth"
        )

    path = Path(credentials_path)
    if not path.exists():
        raise FileNotFoundError(f"Google credentials file not found: {credentials_path}")

    credentials = Credentials.from_service_account_file(
        str(path),
        scopes=SCOPES
    )

    return gspread.authorize(credentials)


def push_to_sheets(events: dict[str, dict], config: dict) -> None:
    """
    Push all events to a Google Sheet (clear and rewrite).

    Args:
        events: Dictionary of events keyed by event_url
        config: Google Sheets configuration containing:
            - spreadsheet_id: ID of the target spreadsheet
            - credentials_path: Path to service account JSON
            - worksheet_name: Name of the worksheet (default: "Events")
    """
    if not GSPREAD_AVAILABLE:
        print("Warning: gspread not installed. Skipping Google Sheets push.")
        return

    spreadsheet_id = config.get("spreadsheet_id")
    credentials_path = config.get("credentials_path", "google_credentials.json")
    worksheet_name = config.get("worksheet_name", "Events")

    if not spreadsheet_id:
        print("Warning: No spreadsheet_id configured. Skipping Google Sheets push.")
        return

    try:
        client = authenticate(credentials_path)
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=worksheet_name,
                rows=1000,
                cols=15
            )

        # Clear existing content
        worksheet.clear()

        # Prepare header and data
        headers = [
            "Title",
            "Date",
            "Time",
            "Event URL",
            "Description",
            "Venue",
            "Address",
            "Online",
            "Group Name",
            "Group URL",
            "Sales Rep",
            "Status",
        ]

        # Convert events dict to sorted list
        event_list = sorted(
            events.values(),
            key=lambda x: x.get("date", "9999-99-99")
        )

        # Build rows
        rows = [headers]
        for event in event_list:
            rows.append([
                event.get("title", ""),
                event.get("date", ""),
                event.get("time", ""),
                event.get("event_url", ""),
                event.get("description", ""),
                event.get("venue_name", ""),
                event.get("address", ""),
                str(event.get("is_online", False)),
                event.get("group_name", ""),
                event.get("group_url", ""),
                event.get("sales_rep", ""),
                event.get("status", "UPCOMING"),
            ])

        # Write all data at once
        worksheet.update(rows, value_input_option="RAW")

        print(f"Pushed {len(event_list)} events to Google Sheets")

    except Exception as e:
        print(f"Error pushing to Google Sheets: {e}")
