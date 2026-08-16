from django.db.models import Count, Q
from django.http import HttpResponse
from apps.emails.models import EmailMessage
from apps.extraction.models import ExtractedTask
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from apps.extraction.services.diff import compute_edited_fields
from apps.extraction.services.participants import participants_from_email
from .forms import TaskEditForm
from django.utils import timezone as dj_timezone
from apps.calendarsync.services.calendar_client import (
    CalendarError, create_event,
)
from django.db.models import Avg
from apps.extraction.models import ExtractionRun
from django.conf import settings
from django.db import transaction
from apps.emails.services.imap_client import fetch_raw_messages
from apps.emails.services.parser import parse_email
from apps.extraction.services.llm_client import get_client
from apps.extraction.services.parser import ParseError, parse_response
from apps.extraction.services.prompts import get_prompt
from apps.extraction.models import ExtractionRun


def email_list(request):
    status_filter = request.GET.get("status", "")

    qs = (
        EmailMessage.objects
        .annotate(
            task_count=Count("tasks", distinct=True),
            pending_count=Count(
                "tasks",
                filter=Q(tasks__status=ExtractedTask.Status.PENDING),
                distinct=True,
            ),
        )
        .order_by("-received_at")
    )

    if status_filter:
        qs = qs.filter(status=status_filter)

    total_pending = ExtractedTask.objects.filter(
        status=ExtractedTask.Status.PENDING
    ).count()

    context = {
        "nav": "emails",
        "emails": qs[:100],
        "status_filter": status_filter,
        "statuses": EmailMessage.Status.choices,
        "total_pending": total_pending,
    }
    return render(request, "web/email_list.html", context)


def email_detail(request, pk):
    email = get_object_or_404(EmailMessage, pk=pk)

    tasks = (
        email.tasks
        .select_related("run")
        .order_by("status", "due_at")
    )

    context = {
        "nav": "emails",
        "email": email,
        "tasks": tasks,
        "latest_run": email.runs.first(),
    }
    return render(request, "web/email_detail.html", context)


def task_edit(request, pk):
    task = get_object_or_404(
        ExtractedTask.objects.select_related("email"), pk=pk
    )
    available = participants_from_email(task.email)

    if request.method == "POST":
        form = TaskEditForm(request.POST, instance=task)
        if form.is_valid():
            changed = compute_edited_fields(task, form.cleaned_data)

            task = form.save(commit=False)
            task.edited_fields = changed
            task.was_edited = bool(changed)

            selected = request.POST.getlist("attendees")
            task.attendee_emails = [a for a in selected if a in available]
            task.invite_attendees = bool(
                request.POST.get("invite_attendees") and task.attendee_emails
            )

            task.save()

            if changed:
                messages.success(
                    request,
                    "Spremljeno. Ispravljeno: " + ", ".join(changed),
                )
            else:
                messages.success(request, "Spremljeno bez izmjena.")

            return redirect("web:email_detail", pk=task.email_id)
    else:
        form = TaskEditForm(instance=task)
        if not task.attendee_emails:
            task.attendee_emails = available

    context = {
        "nav": "emails",
        "task": task,
        "form": form,
        "available_attendees": available,
    }
    return render(request, "web/task_edit.html", context)


def task_action(request, pk):
    if request.method != "POST":
        return redirect("web:email_list")

    task = get_object_or_404(
        ExtractedTask.objects.select_related("email"), pk=pk
    )
    action = request.POST.get("action")

    if action == "confirm":
        task.status = ExtractedTask.Status.CONFIRMED
        task.save(update_fields=["status"])
        messages.success(request, "Zadatak potvrđen.")

    elif action == "reject":
        task.status = ExtractedTask.Status.REJECTED
        task.save(update_fields=["status"])
        messages.warning(request, "Zadatak odbijen.")

    elif action == "sync":
        if task.due_at is None:
            messages.error(
                request,
                "Zadatak nema rok pa se ne može dodati u kalendar. "
                "Otvori Uredi i postavi datum.",
            )
        else:
            try:
                event = create_event(task)
            except CalendarError as exc:
                messages.error(request, f"Dodavanje nije uspjelo: {exc}")
            else:
                task.calendar_event_id = event.get("id", "")
                task.synced_at = dj_timezone.now()
                task.status = ExtractedTask.Status.SYNCED
                task.save(update_fields=[
                    "calendar_event_id", "synced_at", "status",
                ])
                if task.invite_attendees and task.attendee_emails:
                    messages.success(
                        request,
                        "Dodano u kalendar. Pozivnice poslane: "
                        + ", ".join(task.attendee_emails),
                    )
                else:
                    messages.success(request, "Dodano u kalendar.")

    return redirect("web:email_detail", pk=task.email_id)


def evaluation(request):
    FIELD_LABELS = [
        ("title", "Naziv zadatka"),
        ("due_at", "Datum i vrijeme"),
        ("assignee", "Osoba"),
        ("is_all_day", "Cjelodnevno"),
    ]

    all_tasks = ExtractedTask.objects.exclude(raw_payload={})
    total = all_tasks.count()

    reviewed = all_tasks.exclude(status=ExtractedTask.Status.PENDING)
    reviewed_count = reviewed.count()

    accepted = reviewed.exclude(status=ExtractedTask.Status.REJECTED)
    accepted_count = accepted.count()

    edited_lists = list(accepted.values_list("edited_fields", flat=True))

    field_stats = []
    for field, label in FIELD_LABELS:
        wrong = sum(
            1 for fields in edited_lists if fields and field in fields
        )
        accuracy = (
            100.0 * (accepted_count - wrong) / accepted_count
            if accepted_count else None
        )
        field_stats.append({
            "label": label,
            "field": field,
            "wrong": wrong,
            "accuracy": accuracy,
        })

    rejected = reviewed.filter(status=ExtractedTask.Status.REJECTED).count()
    edited_any = accepted.filter(was_edited=True).count()

    run_stats = []
    seen = (
        ExtractionRun.objects
        .exclude(model_name="manual")
        .order_by()
        .values("model_name", "prompt_version")
        .distinct()
    )
    for key in seen:
        subset = ExtractionRun.objects.filter(**key)
        n = subset.count()
        ok = subset.filter(parsed_ok=True).count()
        agg = subset.aggregate(
            lat=Avg("latency_ms"),
            tin=Avg("input_tokens"),
            tout=Avg("output_tokens"),
        )
        run_stats.append({
            "model": key["model_name"],
            "prompt": key["prompt_version"],
            "runs": n,
            "ok": ok,
            "parse_rate": 100.0 * ok / n if n else 0,
            "latency": agg["lat"],
            "tin": agg["tin"],
            "tout": agg["tout"],
        })
    run_stats.sort(key=lambda r: (r["model"], r["prompt"]))

    context = {
        "nav": "evaluation",
        "total": total,
        "reviewed_count": reviewed_count,
        "pending_count": total - reviewed_count,
        "accepted_count": accepted_count,
        "field_stats": field_stats,
        "rejected": rejected,
        "rejection_rate": (
            100.0 * rejected / reviewed_count if reviewed_count else None
        ),
        "edited_any": edited_any,
        "clean_rate": (
            100.0 * (accepted_count - edited_any) / accepted_count
            if accepted_count else None
        ),
        "run_stats": run_stats,
        "conf_edited": accepted.filter(was_edited=True).aggregate(
            v=Avg("confidence"))["v"],
        "conf_clean": accepted.filter(was_edited=False).aggregate(
            v=Avg("confidence"))["v"],
    }
    return render(request, "web/evaluation.html", context)

def refresh(request):
    if request.method != "POST":
        return redirect("web:email_list")

    do_fetch = request.POST.get("fetch") == "1"
    do_analyze = request.POST.get("analyze") == "1"

    if do_fetch:
        try:
            created, skipped, failed = _fetch_new_emails(limit=20)
        except Exception as exc:
            messages.error(request, f"Dohvat nije uspio: {exc}")
        else:
            if created:
                messages.success(
                    request,
                    f"Dohvaćeno {created} novih poruka."
                    + (f" Neuspjelih: {failed}." if failed else ""),
                )
            else:
                messages.info(request, "Nema novih poruka.")

    if do_analyze:
        ok, fail, tasks = _analyze_pending(limit=10)
        if ok or fail:
            messages.success(
                request,
                f"Analizirano {ok} poruka, prepoznato {tasks} zadataka."
                + (f" Neuspjelih: {fail}." if fail else ""),
            )
        else:
            messages.info(request, "Nema poruka za analizu.")

    return redirect("web:email_list")


def _fetch_new_emails(limit=20):
    created = skipped = failed = 0

    for uid, raw in fetch_raw_messages(limit=limit):
        try:
            parsed = parse_email(raw, uid=uid)
        except Exception:
            failed += 1
            continue

        with transaction.atomic():
            _, was_created = EmailMessage.objects.get_or_create(
                message_id=parsed["message_id"], defaults=parsed
            )
        if was_created:
            created += 1
        else:
            skipped += 1

    return created, skipped, failed


def _analyze_pending(limit=10):
    prompt_version = settings.PROMPT_VERSION
    prompt = get_prompt(prompt_version)
    client = get_client()

    emails = list(
        EmailMessage.objects
        .filter(status=EmailMessage.Status.FETCHED)
        .order_by("-received_at")[:limit]
    )

    ok = fail = task_total = 0

    for email in emails:
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
                fail += 1
                continue

            try:
                tasks = parse_response(response.raw_text)
            except ParseError as exc:
                run.error = str(exc)
                run.save(update_fields=["error"])
                email.status = EmailMessage.Status.FAILED
                email.error = str(exc)
                email.save(update_fields=["status", "error"])
                fail += 1
                continue

            for data in tasks:
                ExtractedTask.objects.create(email=email, run=run, **data)

            run.parsed_ok = True
            run.save(update_fields=["parsed_ok"])
            email.status = EmailMessage.Status.ANALYZED
            email.error = ""
            email.save(update_fields=["status", "error"])

        ok += 1
        task_total += len(tasks)

    return ok, fail, task_total