from django import forms
from .models import MaintenanceSchedule

class MaintenanceScheduleForm(forms.ModelForm):
    class Meta:
        model = MaintenanceSchedule
        fields = ['title', 'frequency', 'next_run_date', 'maintenance_type', 'asset', 'infrastructure', 'assigned_to', 'checklist', 'description', 'is_active']
        widgets = {
            'next_run_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'checklist': forms.HiddenInput(),
        }
        help_texts = {
            'checklist': 'Format: [{"task": "Check Cable", "done": false}, ...]. Leave empty [] if none.'
        }

    def clean_checklist(self):
        data = self.cleaned_data['checklist']
        if not data:
            return []
        if isinstance(data, list):
            return data
        # If it's a string, Django's JSONField should have already parsed it if entered in valid JSON format.
        # But sometimes it might come as a string if validation failed earlier?
        # Standard JSONField handles parsing transparently.
        return data
