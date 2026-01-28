"""Slack notifications for new meetup events."""

import json
from typing import Optional

import requests


def format_event_message(events: list[dict]) -> dict:
    """
    Format events as a Slack Block Kit message.

    Args:
        events: List of event dictionaries

    Returns:
        Slack Block Kit message payload
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"New Meetup Events Found ({len(events)})",
                "emoji": True
            }
        },
        {
            "type": "divider"
        }
    ]

    for event in events[:10]:  # Limit to 10 events to avoid message size limits
        title = event.get("title", "Untitled Event")
        date = event.get("date", "TBD")
        time = event.get("time", "")
        url = event.get("event_url", "")
        group = event.get("group_name", "")
        sales_rep = event.get("sales_rep", "Unassigned")
        venue = event.get("venue_name", "")
        is_online = event.get("is_online", False)

        location = "Online" if is_online else (venue or "TBD")
        datetime_str = f"{date} at {time}" if time else date

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*<{url}|{title}>*\n"
                    f"Date: {datetime_str}\n"
                    f"Location: {location}\n"
                    f"Group: {group}\n"
                    f"Sales Rep: *{sales_rep}*"
                )
            }
        })
        blocks.append({"type": "divider"})

    if len(events) > 10:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_... and {len(events) - 10} more events_"
                }
            ]
        })

    return {"blocks": blocks}


def send_notification(
    webhook_url: str,
    new_events: list[dict],
    timeout: int = 30
) -> Optional[bool]:
    """
    Send a Slack notification about new events.

    Args:
        webhook_url: Slack incoming webhook URL
        new_events: List of newly discovered events
        timeout: Request timeout in seconds

    Returns:
        True if successful, False if failed, None if no events to send
    """
    if not new_events:
        return None

    if not webhook_url:
        print("Warning: No Slack webhook URL configured. Skipping notification.")
        return None

    try:
        message = format_event_message(new_events)

        response = requests.post(
            webhook_url,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )

        if response.status_code == 200:
            print(f"Sent Slack notification for {len(new_events)} new events")
            return True
        else:
            print(f"Slack notification failed: {response.status_code} - {response.text}")
            return False

    except requests.RequestException as e:
        print(f"Error sending Slack notification: {e}")
        return False
