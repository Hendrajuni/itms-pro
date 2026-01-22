from django import forms
from django.forms import inlineformset_factory
from .models import DailyLog, DailyLogItem
from assets.models import Asset, Infrastructure

class DailyLogForm(forms.ModelForm):
    class Meta:
        model = DailyLog
        fields = ['date', 'shift', 'executor', 'work_location', 'status', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'executor': forms.Select(attrs={'class': 'form-select'}), # User select
            'work_location': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional: General summary of the day...'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(DailyLogForm, self).__init__(*args, **kwargs)
        
        if self.user and not self.user.is_superuser:
            # Restrict Status choices for non-admin
            # Only allow 'Draft' and 'Submitted'
            allowed_choices = [('Draft', 'Draft'), ('Submitted', 'Submitted')]
            
            # Use choice field logic to restrict
            self.fields['status'].choices = allowed_choices

class DailyLogItemForm(forms.ModelForm):
    class Meta:
        model = DailyLogItem
        fields = ['task_name', 'category', 'start_time', 'end_time', 'status', 'related_asset', 'related_infra', 'note']
        widgets = {
            'task_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task description'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'related_asset': forms.Select(attrs={'class': 'form-select'}), 
            'related_infra': forms.Select(attrs={'class': 'form-select'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 1, 'placeholder': 'Notes'}),
        }

# Inline FormSet for Items
DailyLogItemFormSet = inlineformset_factory(
    DailyLog, 
    DailyLogItem, 
    form=DailyLogItemForm,
    extra=1, 
    can_delete=True
)

from .models import Project, ProjectTask

class ProjectTaskForm(forms.ModelForm):
    class Meta:
        model = ProjectTask
        fields = ['name', 'assigned_to', 'status', 'due_date', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task Name'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 1, 'placeholder': 'Optional description'}),
        }

ProjectTaskFormSet = inlineformset_factory(
    Project,
    ProjectTask,
    form=ProjectTaskForm,
    extra=1,
    can_delete=True
)
