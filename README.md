# Meetup Event Scraper

Scrapes upcoming events from Meetup.com groups and exports them to CSV with sales rep assignments.

## Features

- Scrapes multiple Meetup groups in one run
- Extracts event details: title, date, time, venue, description, etc.
- Assigns sales reps to events based on config
- Deduplicates groups and events automatically
- Exports to CSV sorted by date

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

## How It Works

The scraper uses Browserless to render Meetup pages (which require JavaScript), then extracts event data from Meetup's embedded `__NEXT_DATA__` JSON rather than parsing HTML. This makes it more reliable and faster than traditional HTML scraping.
