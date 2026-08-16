from django.utils import timezone

TRACKED_FIELDS = ["title", "due_at", "assignee", "is_all_day"]


def _normalize(field, value):
    if value is None or value == "":
        return None

    if field == "due_at":
        if hasattr(value, "isoformat"):
            return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
        text = str(value).strip().replace("T", " ").replace("Z", "")
        return text[:16]

    if field == "is_all_day":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    return str(value).strip().casefold()


def compute_edited_fields(task, cleaned_data):
    payload = task.raw_payload or {}
    if not payload:
        return []

    changed = []

    for field in TRACKED_FIELDS:
        if field not in payload:
            continue
        original = _normalize(field, payload.get(field))
        submitted = _normalize(field, cleaned_data.get(field))
        if original != submitted:
            changed.append(field)

    return changed