from django import forms
from apps.extraction.models import ExtractedTask

class TaskEditForm(forms.ModelForm):
    class Meta:
        model = ExtractedTask
        fields = ["title", "description", "due_at", "is_all_day", "assignee"]
        widgets = {
            "due_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title": "Naziv zadatka",
            "description": "Opis",
            "due_at": "Rok",
            "is_all_day": "Cjelodnevni događaj",
            "assignee": "Osoba",
        }

def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["due_at"].widget.format = "%Y-%m-%dT%H:%M"
        self.fields["due_at"].widget.attrs["type"] = "datetime-local"
        self.fields["due_at"].required = False
        self.fields["description"].required = False
        self.fields["assignee"].required = False