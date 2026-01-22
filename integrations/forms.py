from django import forms
from .models import WhatsAppConfig, TelegramConfig, EmailConfig

class WhatsAppForm(forms.ModelForm):
    api_token = forms.CharField(widget=forms.PasswordInput(render_value=True), help_text="API Authorization Token")

    class Meta:
        model = WhatsAppConfig
        fields = ['api_url', 'api_token', 'default_target_number', 'is_active']
        widgets = {
            'api_url': forms.TextInput(attrs={'placeholder': 'https://api.fonnte.com/send'}),
            'default_target_number': forms.TextInput(attrs={'placeholder': '62812xxxx'}),
        }

class TelegramForm(forms.ModelForm):
    bot_token = forms.CharField(widget=forms.PasswordInput(render_value=True), help_text="Bot Token from @BotFather")
    
    class Meta:
        model = TelegramConfig
        fields = ['bot_token', 'chat_id', 'is_active']
        widgets = {
            'chat_id': forms.TextInput(attrs={'placeholder': '-100xxxx or User ID'}),
        }

class EmailConfigForm(forms.ModelForm):
    smtp_password = forms.CharField(widget=forms.PasswordInput(render_value=True), help_text="SMTP Password")

    class Meta:
        model = EmailConfig
        fields = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'use_tls', 'default_from_email', 'is_active']
        widgets = {
            'smtp_host': forms.TextInput(attrs={'placeholder': 'smtp.gmail.com'}),
            'smtp_port': forms.NumberInput(attrs={'placeholder': '587'}),
            'smtp_user': forms.TextInput(attrs={'placeholder': 'email@example.com'}),
            'default_from_email': forms.TextInput(attrs={'placeholder': 'noreply@example.com'}),
        }
