from django.db import models

class EmailMessage(models.Model):
    class Status(models.TextChoices):
        FETCHED = "fetched", "Fetched"
        ANALYZING = "analyzing", "Analyzing"
        ANALYZED = "analyzed", "Analyzed"
        FAILED = "failed", "Failed"

    # --- identity / dedup ---
    message_id = models.CharField(max_length=998, unique=True, db_index=True)
    uid = models.IntegerField(null=True, blank=True)
    folder = models.CharField(max_length=255, default="INBOX")

    # --- headers ---
    subject = models.CharField(max_length=998, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    sender_email = models.CharField(max_length=320, blank=True)
    recipients = models.JSONField(default=list, blank=True)

    # --- content ---
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    raw_source = models.BinaryField(null=True, blank=True)

    # --- timestamps ---
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    # --- pipeline state ---
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.FETCHED, db_index=True
    )
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.subject or '(no subject)'} — {self.sender_email}"