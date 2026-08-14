from django.contrib import admin
from .models import ExtractionRun, ExtractedTask

class ExtractedTaskInline(admin.TabularInline):
    model = ExtractedTask
    fk_name = "run"
    extra = 0
    fields = ("title", "due_at", "assignee", "status", "confidence")

@admin.register(ExtractionRun)
class ExtractionRunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "email", "model_name", "prompt_version",
        "parsed_ok", "latency_ms", "created_at",
    )
    list_filter = ("model_name", "prompt_version", "parsed_ok")
    readonly_fields = ("created_at",)
    inlines = [ExtractedTaskInline]

@admin.register(ExtractedTask)
class ExtractedTaskAdmin(admin.ModelAdmin):
    list_display = (
        "title", "due_at", "assignee", "status", "was_edited", "confidence",
    )
    list_filter = ("status", "was_edited", "is_all_day")
    search_fields = ("title", "assignee")
    readonly_fields = ("raw_payload", "created_at")