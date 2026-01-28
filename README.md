# Meetup Event Scraper

Scrapes upcoming events from Meetup.com groups and exports them to CSV with sales rep assignments. Supports state persistence, Google Sheets integration, Slack notifications, and calendar file generation.

## Features

- Scrapes multiple Meetup groups in one run
- Extracts event details: title, date, time, venue, description, etc.
- Assigns sales reps to events based on config
- Deduplicates groups and events automatically
- **State persistence**: Tracks events across runs, only adds new ones
- **Status tracking**: Automatically marks past events as DONE
- **Google Sheets**: Push events to a shared spreadsheet
- **Slack notifications**: Get alerts when new events are discovered
- **Calendar files**: Generate .ics files for new events
- **Google Calendar**: Sync events and send invites to sales reps

## Requirements

- Python 3.10+
- [Browserless](https://browserless.io/) API key (for JavaScript rendering)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy the example config and add your API key:
   ```bash
   cp config.example.json config.json
   ```

3. Edit `config.json` with your Browserless API key and Meetup groups:
   ```json
   {
     "browserless_api_key": "YOUR_API_KEY",
     "groups": [
       {
         "url": "https://www.meetup.com/your-group/",
         "sales_rep": "John Smith"
       }
     ]
   }
   ```

## Usage

```bash
python scraper.py
```

Output is written to `events.csv` with the following columns:

| Field | Description |
|-------|-------------|
| title | Event name |
| date | Event date (YYYY-MM-DD) |
| time | Event time (HH:MM) |
| event_url | Direct link to event |
| description | Event description (truncated to 500 chars) |
| venue_name | Venue name or "Online" |
| address | Full address or empty for online events |
| is_online | True/False |
| group_name | Meetup group name |
| group_url | Group URL |
| sales_rep | Assigned sales rep from config |
| status | UPCOMING or DONE |

## Optional Integrations

### Google Sheets

Push events to a Google Spreadsheet for team visibility.

1. Create a Google Cloud service account and download the JSON credentials
2. Share your spreadsheet with the service account email
3. Configure in `config.json`:
   ```json
   {
     "google_sheets": {
       "enabled": true,
       "spreadsheet_id": "YOUR_SPREADSHEET_ID",
       "credentials_path": "google_credentials.json",
       "worksheet_name": "Events"
     }
   }
   ```

The spreadsheet ID is in the URL: `docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`

### Slack Notifications

Get notified when new events are discovered.

1. Create an [Incoming Webhook](https://api.slack.com/messaging/webhooks) in Slack
2. Configure in `config.json`:
   ```json
   {
     "slack": {
       "enabled": true,
       "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
     }
   }
   ```

### Calendar Files

Generate .ics files for new events that can be imported into any calendar app.

1. Configure in `config.json`:
   ```json
   {
     "calendar": {
       "enabled": true,
       "output_dir": "calendars",
       "default_duration_hours": 2
     },
     "rep_emails": {
       "John Smith": "john@company.com",
       "Jane Doe": "jane@company.com"
     }
   }
   ```

Calendar files are saved to the `calendars/` directory.

### Google Calendar (with Invites)

Sync events directly to Google Calendar and send invites to sales reps.

1. Create a Google Cloud service account (same as for Sheets)
2. Enable the Google Calendar API in your Google Cloud project
3. Share your calendar with the service account email (or use "primary" for your main calendar)
4. Configure in `config.json`:
   ```json
   {
     "rep_emails": {
       "John Smith": "john@company.com",
       "Jane Doe": "jane@company.com"
     },
     "google_calendar": {
       "enabled": true,
       "calendar_id": "primary",
       "credentials_path": "google_credentials.json",
       "default_duration_hours": 2,
       "send_invites": true
     }
   }
   ```

Each sales rep will receive an email invite for events assigned to them.

## How It Works

The scraper uses Browserless to render Meetup pages (which require JavaScript), then extracts event data from Meetup's embedded `__NEXT_DATA__` JSON rather than parsing HTML. This makes it more reliable and faster than traditional HTML scraping.

### State Management

- On each run, existing events are loaded from `events.csv`
- Past events are marked as `DONE`, future events as `UPCOMING`
- Only truly new events (by URL) are added to the database
- Integrations (Slack, calendars) only process newly discovered events

## Project Structure

```
meetup-scraper/
├── scraper.py              # Main orchestrator
├── config.json             # Your configuration (gitignored)
├── config.example.json     # Template configuration
├── events.csv              # Event database (gitignored)
├── requirements.txt        # Python dependencies
├── calendars/              # Generated .ics files (gitignored)
└── modules/
    ├── __init__.py
    ├── csv_manager.py      # State persistence, status tracking
    ├── google_sheets.py    # Google Sheets integration
    ├── google_calendar.py  # Google Calendar with invites
    ├── slack_notifier.py   # Slack notifications
    └── calendar_generator.py # ICS file generation
```
