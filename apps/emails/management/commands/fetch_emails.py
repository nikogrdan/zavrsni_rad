from django.core.management.base import BaseCommand
from django.db import transaction

from apps.emails.models import EmailMessage
from apps.emails.services.imap_client import fetch_raw_messages
from apps.emails.services.parser import parse_email


class Command(BaseCommand):
    help = "Fetch messages from the configured IMAP mailbox into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=20,
            help="Maximum number of messages to fetch (default: 20).",
        )
        parser.add_argument(
            "--since-days", type=int, default=None,
            help="Only fetch messages received in the last N days.",
        )
        parser.add_argument(
            "--unseen", action="store_true",
            help="Only fetch unread messages.",
        )

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0
        failed_count = 0

        try:
            messages = fetch_raw_messages(
                limit=options["limit"],
                since_days=options["since_days"],
                unseen_only=options["unseen"],
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"IMAP connection failed: {exc}"))
            return

        for uid, raw in messages:
            try:
                parsed = parse_email(raw, uid=uid)
            except Exception as exc:
                failed_count += 1
                self.stderr.write(self.style.WARNING(f"UID {uid}: parse failed — {exc}"))
                continue

            with transaction.atomic():
                obj, created = EmailMessage.objects.get_or_create(
                    message_id=parsed["message_id"],
                    defaults=parsed,
                )

            if created:
                created_count += 1
                subject = (obj.subject or "(no subject)")[:70]
                self.stdout.write(f"  + {subject}")
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_count} new, {skipped_count} already known, "
                f"{failed_count} failed."
            )
        )