from django import forms
from .models import Ticket, TicketComment

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['topic', 'title', 'description', 'asset', 'attachment', 'priority']
        widgets = {
            'topic': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Issue Summary'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'asset': forms.Select(attrs={'class': 'form-select'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            from assets.models import Asset
            self.fields['asset'].queryset = Asset.objects.filter(assigned_to=user)
            self.fields['asset'].empty_label = "Choose an asset (Optional)"

class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['message', 'attachment']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Type your reply here...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
