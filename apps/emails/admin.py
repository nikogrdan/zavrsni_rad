from django.contrib import admin
from .models import EmailMessage

@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender_email", "received_at", "status")
    list_filter = ("status", "folder")
    search_fields = ("subject", "sender_email", "body_text")
    readonly_fields = ("fetched_at", "raw_source")
    date_hierarchy = "received_at"