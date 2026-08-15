from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.calendarsync.services.calendar_client import CalendarError, create_event
from apps.extraction.models import ExtractedTask


class Command(BaseCommand):
    help = "Dodaj potvrđene zadatke u Google kalendar."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--task-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        qs = ExtractedTask.objects.select_related("email")

        if options["task_id"]:
            qs = qs.filter(id=options["task_id"])
        else:
            qs = qs.filter(
                status=ExtractedTask.Status.CONFIRMED,
                due_at__isnull=False,
            )

        tasks = list(qs[:options["limit"]])

        if not tasks:
            self.stdout.write(
                "Nema potvrđenih zadataka s datumom za sinkronizaciju."
            )
            return

        if options["dry_run"]:
            self.stdout.write(f"Probni rad — {len(tasks)} zadataka:\n")
            for task in tasks:
                kind = "cjelodnevni" if task.is_all_day else "s vremenom"
                self.stdout.write(
                    f"  {task.title[:45]:47} "
                    f"{timezone.localtime(task.due_at):%d.%m.%Y %H:%M} ({kind})"
                )
            return

        ok_count = 0
        fail_count = 0

        for task in tasks:
            if task.calendar_event_id:
                self.stdout.write(
                    f"  = {task.title[:45]} — već sinkronizirano, preskačem"
                )
                continue

            try:
                event = create_event(task)
            except CalendarError as exc:
                fail_count += 1
                self.stderr.write(
                    self.style.ERROR(f"  x {task.title[:45]} — {exc}")
                )
                continue

            task.calendar_event_id = event.get("id", "")
            task.synced_at = timezone.now()
            task.status = ExtractedTask.Status.SYNCED
            task.save(
                update_fields=["calendar_event_id", "synced_at", "status"]
            )
            ok_count += 1
            self.stdout.write(
                f"  + {task.title[:45]:47} {event.get('htmlLink', '')}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nGotovo. {ok_count} dodano, {fail_count} neuspješno."
            )
        )