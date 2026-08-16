from django.db import models

class ExtractionRun(models.Model):
    email = models.ForeignKey(
        "emails.EmailMessage", on_delete=models.CASCADE, related_name="runs"
    )
    model_name = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20)

    raw_response = models.TextField(blank=True)
    parsed_ok = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    latency_ms = models.IntegerField(null=True, blank=True)
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model_name}/{self.prompt_version} on #{self.email_id}"


class ExtractedTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        SYNCED = "synced", "Synced to calendar"

    email = models.ForeignKey(
        "emails.EmailMessage", on_delete=models.CASCADE, related_name="tasks"
    )
    run = models.ForeignKey(
        ExtractionRun, on_delete=models.CASCADE, related_name="tasks"
    )

    raw_payload = models.JSONField(default=dict)

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    assignee = models.CharField(max_length=255, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    invite_attendees = models.BooleanField(default=False)
    attendee_emails = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    was_edited = models.BooleanField(default=False)
    edited_fields = models.JSONField(default=list, blank=True)

    calendar_event_id = models.CharField(max_length=255, blank=True, null=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_at", "-created_at"]

    def __str__(self):
        return self.title