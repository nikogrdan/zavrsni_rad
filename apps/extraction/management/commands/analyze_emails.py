from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.emails.models import EmailMessage
from apps.extraction.models import ExtractedTask, ExtractionRun
from apps.extraction.services.llm_client import get_client
from apps.extraction.services.parser import ParseError, parse_response
from apps.extraction.services.prompts import get_prompt


class Command(BaseCommand):
    help = "Analiziraj dohvaćene email poruke pomoću LLM-a i izvuci zadatke."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--model", type=str, default=None)
        parser.add_argument("--prompt-version", type=str, default=None)
        parser.add_argument("--reanalyze", action="store_true")
        parser.add_argument("--email-id", type=int, default=None)

    def handle(self, *args, **options):
        prompt_version = options["prompt_version"] or settings.PROMPT_VERSION
        prompt = get_prompt(prompt_version)
        client = get_client(model=options["model"])

        qs = EmailMessage.objects.all()
        if options["email_id"]:
            qs = qs.filter(id=options["email_id"])
        elif not options["reanalyze"]:
            qs = qs.filter(status=EmailMessage.Status.FETCHED)
        qs = qs.order_by("-received_at")[:options["limit"]]

        emails = list(qs)
        if not emails:
            self.stdout.write("Nema poruka za analizu.")
            return

        model_label = options["model"] or settings.LLM_MODEL
        self.stdout.write(
            f"Analiziram {len(emails)} poruka "
            f"(provider: {settings.LLM_PROVIDER}, model: {model_label}, "
            f"prompt: {prompt_version})\n"
        )

        ok_count = 0
        fail_count = 0
        task_count = 0

        for email in emails:
            EmailMessage.objects.filter(pk=email.pk).update(
                status=EmailMessage.Status.ANALYZING
            )

            user_msg = prompt["user_template"].format(
                received_at=(
                    email.received_at.isoformat() if email.received_at else "nepoznat"
                ),
                sender=f"{email.sender_name} <{email.sender_email}>".strip(),
                recipients=", ".join(
                    r.get("email", "") for r in email.recipients
                ) or "-",
                subject=email.subject or "(bez predmeta)",
                body=(email.body_text or email.body_html or "")[:8000],
            )

            response = client.complete(prompt["system"], user_msg)

            with transaction.atomic():
                run = ExtractionRun.objects.create(
                    email=email,
                    model_name=response.model_name,
                    prompt_version=prompt_version,
                    raw_response=response.raw_text,
                    error=response.error,
                    latency_ms=response.latency_ms,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    parsed_ok=False,
                )

                if response.error:
                    email.status = EmailMessage.Status.FAILED
                    email.error = response.error
                    email.save(update_fields=["status", "error"])
                    fail_count += 1
                    self.stderr.write(
                        self.style.ERROR(
                            f"  x {email.subject[:50]} — API greška"
                        )
                    )
                    continue

                try:
                    tasks = parse_response(response.raw_text)
                except ParseError as exc:
                    run.error = str(exc)
                    run.save(update_fields=["error"])
                    email.status = EmailMessage.Status.FAILED
                    email.error = str(exc)
                    email.save(update_fields=["status", "error"])
                    fail_count += 1
                    self.stderr.write(
                        self.style.WARNING(f"  x {email.subject[:50]} — {exc}")
                    )
                    continue

                for task_data in tasks:
                    ExtractedTask.objects.create(email=email, run=run, **task_data)

                run.parsed_ok = True
                run.save(update_fields=["parsed_ok"])
                email.status = EmailMessage.Status.ANALYZED
                email.error = ""
                email.save(update_fields=["status", "error"])

            ok_count += 1
            task_count += len(tasks)
            label = f"{len(tasks)} zadataka" if tasks else "nema zadataka"
            self.stdout.write(f"  + {email.subject[:50]:52} {label}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nGotovo. {ok_count} uspješno, {fail_count} neuspješno, "
                f"{task_count} zadataka ukupno."
            )
        )