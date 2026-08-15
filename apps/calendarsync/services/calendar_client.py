import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.calendarsync.services.google_auth import get_credentials

logger = logging.getLogger(__name__)

DEFAULT_DURATION_MINUTES = 60


class CalendarError(Exception):
    pass


def _get_service():
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _build_event_body(task):
    tz_name = settings.TIME_ZONE

    if task.due_at is None:
        raise CalendarError(
            f"Zadatak #{task.id} nema datum — ne može se dodati u kalendar."
        )

    summary = task.title[:1000]

    description_parts = []
    if task.description:
        description_parts.append(task.description)
    if task.assignee:
        description_parts.append(f"Osoba: {task.assignee}")
    if task.email_id:
        description_parts.append(f"Iz poruke: {task.email.subject}")
        description_parts.append(f"Pošiljatelj: {task.email.sender_email}")
    if task.confidence is not None:
        description_parts.append(f"Pouzdanost modela: {task.confidence:.2f}")

    body = {
        "summary": summary,
        "description": "\n".join(description_parts),
    }

    if task.is_all_day:
        local_date = timezone.localtime(task.due_at).date()
        body["start"] = {"date": local_date.isoformat()}
        body["end"] = {"date": (local_date + timedelta(days=1)).isoformat()}
        body["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 12 * 60}],
        }
    else:
        start = timezone.localtime(task.due_at)
        end = start + timedelta(minutes=DEFAULT_DURATION_MINUTES)
        body["start"] = {"dateTime": start.isoformat(), "timeZone": tz_name}
        body["end"] = {"dateTime": end.isoformat(), "timeZone": tz_name}
        body["reminders"] = {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30},
            ],
        }

    return body


def create_event(task, calendar_id=None):
    calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
    body = _build_event_body(task)

    try:
        service = _get_service()
        event = service.events().insert(
            calendarId=calendar_id, body=body
        ).execute()
    except HttpError as exc:
        raise CalendarError(f"Google API greška: {exc}") from exc

    logger.info("Kreiran događaj %s za zadatak #%s", event.get("id"), task.id)
    return event


def delete_event(event_id, calendar_id=None):
    calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
    try:
        service = _get_service()
        service.events().delete(
            calendarId=calendar_id, eventId=event_id
        ).execute()
    except HttpError as exc:
        if exc.resp.status in (404, 410):
            logger.info("Događaj %s već ne postoji.", event_id)
            return
        raise CalendarError(f"Google API greška: {exc}") from exc