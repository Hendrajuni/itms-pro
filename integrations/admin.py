from django.contrib import admin
from .models import WhatsAppConfig, TelegramConfig, EmailConfig

@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'api_url', 'is_active')
    fieldsets = (
        (None, {
            'fields': ('api_url', 'api_token', 'default_target_number', 'is_active')
        }),
    )

    def has_add_permission(self, request):
        # Only allow creating if instance doesn't exist
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(TelegramConfig)
class TelegramConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'chat_id', 'is_active')
    fieldsets = (
        (None, {
            'fields': ('bot_token', 'chat_id', 'is_active')
        }),
    )

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(EmailConfig)
class EmailConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'smtp_host', 'smtp_port', 'smtp_user', 'is_active')
    fieldsets = (
        (None, {
            'fields': (
                'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 
                'use_tls', 'default_from_email', 'is_active'
            )
        }),
    )

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
