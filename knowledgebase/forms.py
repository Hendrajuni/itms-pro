from django import forms
from .models import Article
from assets.models import Asset
from ckeditor.widgets import CKEditorWidget

class ArticleForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditorWidget())

    class Meta:
        model = Article
        fields = ['title', 'category', 'visibility', 'status', 'content', 'related_assets']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter article title'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'related_assets': forms.SelectMultiple(attrs={'class': 'form-select select2'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optimize asset loading
        self.fields['related_assets'].queryset = Asset.objects.filter(status__in=['IN_USE', 'AVAILABLE']).order_by('name')
