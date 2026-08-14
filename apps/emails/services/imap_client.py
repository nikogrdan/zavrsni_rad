import logging
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from imapclient import IMAPClient

logger = logging.getLogger(__name__)


@contextmanager
def imap_connection(readonly=True):
    """Connect, log in, select the folder, and always clean up."""
    if not settings.IMAP_USER or not settings.IMAP_PASSWORD:
        raise RuntimeError("IMAP_USER and IMAP_PASSWORD must be set in .env")

    server = IMAPClient(settings.IMAP_HOST, port=settings.IMAP_PORT, ssl=True)
    try:
        server.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        server.select_folder(settings.IMAP_FOLDER, readonly=readonly)
        yield server
    finally:
        try:
            server.logout()
        except Exception:
            pass


def fetch_raw_messages(limit=None, since_days=None, unseen_only=False):
    """Yield (uid, raw_bytes) for messages matching the given criteria."""
    criteria = ["ALL"]
    if unseen_only:
        criteria = ["UNSEEN"]
    if since_days:
        cutoff = (timezone.now() - timedelta(days=since_days)).date()
        criteria += ["SINCE", cutoff]

    with imap_connection(readonly=True) as server:
        uids = server.search(criteria)
        uids = sorted(uids, reverse=True)
        if limit:
            uids = uids[:limit]

        logger.info("Fetching %d message(s) from %s", len(uids), settings.IMAP_FOLDER)

        if not uids:
            return

        for uid, data in server.fetch(uids, ["RFC822"]).items():
            raw = data.get(b"RFC822")
            if raw:
                yield uid, raw