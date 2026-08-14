import email
import hashlib
from email import policy
from email.utils import getaddresses, parsedate_to_datetime

from django.utils import timezone


def _decode_datetime(raw_date):
    """Convert a Date header into a timezone-aware datetime, or None."""
    if not raw_date:
        return None
    try:
        dt = parsedate_to_datetime(str(raw_date))
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _get_body(msg, subtype):
    """Extract text/plain or text/html content, tolerating bad encodings."""
    try:
        part = msg.get_body(preferencelist=(subtype,))
    except Exception:
        return ""
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        content = payload.decode("utf-8", errors="replace")
    return content.strip() if isinstance(content, str) else ""


def parse_email(raw_bytes, uid=None, folder="INBOX"):
    """Turn raw email bytes into a dict matching EmailMessage's fields."""
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)

    # Message-ID is our dedup key. A few senders omit it, so fall back to a
    # content hash — stable across re-fetches of the same message.
    message_id = str(msg["Message-ID"] or "").strip()
    if not message_id:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        message_id = f"<generated-{digest}@local>"

    sender_name, sender_email = "", ""
    from_pairs = getaddresses([str(msg["From"] or "")])
    if from_pairs:
        sender_name, sender_email = from_pairs[0]

    recipient_headers = []
    for header in ("To", "Cc"):
        if msg[header]:
            recipient_headers.append(str(msg[header]))
    recipients = [
        {"name": name, "email": addr}
        for name, addr in getaddresses(recipient_headers)
        if addr
    ]

    return {
        "message_id": message_id[:998],
        "uid": uid,
        "folder": folder,
        "subject": str(msg["Subject"] or "").strip()[:998],
        "sender_name": sender_name[:255],
        "sender_email": sender_email[:320],
        "recipients": recipients,
        "body_text": _get_body(msg, "plain"),
        "body_html": _get_body(msg, "html"),
        "raw_source": raw_bytes,
        "received_at": _decode_datetime(msg["Date"]),
    }