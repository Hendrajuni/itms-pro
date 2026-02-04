from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'photo', 'notes', 'department', 'location', 'job_title']
        widgets = {
            'department': forms.Select(attrs={'disabled': 'disabled'}),
            'location': forms.Select(attrs={'disabled': 'disabled'}),
            'job_title': forms.TextInput(attrs={'disabled': 'disabled'}),
            'email': forms.EmailInput(attrs={'disabled': 'disabled'}), # Email usually managed by admin
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure required fields that are disabled are not required in validation if they weren't submitted
        # Actually, for disabled fields, browsers don't send values.
        # But since we are updating an instance, we just need to ensure we don't accidentally clear them if modelform expects them.
        # Setting disabled in widget is good for UI.
        # For security, we should exclude them from 'fields' and just display them manually, OR use 'read_only' logic.
        # But if we include them in fields and disabled widget, Django might complain if data is missing?
        # Let's clean validation data for disabled fields or just exclude them from the actual save if needed.
        # Actually, best practice for "Read Only" in ModelForm is to set field.disabled = True
        
        self.fields['department'].disabled = True
        self.fields['location'].disabled = True
        self.fields['job_title'].disabled = True
        self.fields['email'].disabled = True
        self.fields['department'].required = False
        self.fields['location'].required = False
        self.fields['job_title'].required = False
        self.fields['email'].required = False

from assets.models import Department

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'manager', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['manager'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['manager'].widget.attrs.update({'class': 'form-select select2'})

from assets.models import DepartmentHead

class RegionalHeadForm(forms.ModelForm):
    class Meta:
        model = DepartmentHead
        fields = ['department', 'location', 'manager']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['manager'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['manager'].widget.attrs.update({'class': 'form-select select2'})
        self.fields['location'].widget.attrs.update({'class': 'form-select select2'})

from django.contrib.auth.forms import UserCreationForm

class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'department', 'location', 'groups']
        widgets = {
             'groups': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].widget.attrs.update({'class': 'form-select select2'})
        self.fields['location'].widget.attrs.update({'class': 'form-select select2'})
        self.fields['email'].required = True

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'department', 'location', 'groups', 'is_active', 'is_staff', 'is_superuser']
        widgets = {
             'groups': forms.CheckboxSelectMultiple(),
             'department': forms.Select(attrs={'class': 'form-select select2'}),
             'location': forms.Select(attrs={'class': 'form-select select2'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

