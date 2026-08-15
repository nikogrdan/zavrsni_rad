import json
import logging
import re
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_TITLE_LEN = 500
MAX_ASSIGNEE_LEN = 255


class ParseError(Exception):
    pass


def _strip_fences(text):
    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    return text


def _parse_datetime(value):
    if not value:
        return None
    if not isinstance(value, str):
        return None

    cleaned = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        logger.warning("Neispravan datum iz modela: %r", value)
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_confidence(value):
    if value is None:
        return None
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, conf))


def _clean_task(item):
    if not isinstance(item, dict):
        return None

    title = str(item.get("title") or "").strip()
    if not title:
        return None

    due_at = _parse_datetime(item.get("due_at"))
    is_all_day = bool(item.get("is_all_day", False))

    if due_at is None:
        is_all_day = False

    return {
        "title": title[:MAX_TITLE_LEN],
        "description": str(item.get("description") or "").strip(),
        "due_at": due_at,
        "is_all_day": is_all_day,
        "assignee": str(item.get("assignee") or "").strip()[:MAX_ASSIGNEE_LEN],
        "confidence": _parse_confidence(item.get("confidence")),
        "raw_payload": item,
    }


def parse_response(raw_text):
    if not raw_text or not raw_text.strip():
        raise ParseError("Prazan odgovor modela")

    cleaned = _strip_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Neispravan JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ParseError(f"Očekivan JSON objekt, dobiven {type(data).__name__}")

    tasks_raw = data.get("tasks")
    if tasks_raw is None:
        raise ParseError("Nedostaje ključ 'tasks'")
    if not isinstance(tasks_raw, list):
        raise ParseError(
            f"Ključ 'tasks' mora biti lista, dobiven {type(tasks_raw).__name__}"
        )

    tasks = []
    for item in tasks_raw:
        cleaned_task = _clean_task(item)
        if cleaned_task is not None:
            tasks.append(cleaned_task)
        else:
            logger.warning("Preskočen neispravan zadatak: %r", item)

    return tasks