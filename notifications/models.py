from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# class TelegramConfig(models.Model):
#     bot_token = models.CharField(max_length=200, help_text="API Token from BotFather")
#     alert_chat_id = models.CharField(max_length=100, help_text="Target Chat ID (e.g., -100xxxx)")
#     is_active = models.BooleanField(default=True)
#     description = models.CharField(max_length=200, default="IT Team Group")
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     def save(self, *args, **kwargs):
#         # Singleton Logic: Ensure only one active config
#         if self.is_active:
#             TelegramConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
#         super().save(*args, **kwargs)
#
#     def __str__(self):
#         return f"{self.description} ({'Active' if self.is_active else 'Inactive'})"
#
#     class Meta:
#         verbose_name = "Telegram Configuration"
#         verbose_name_plural = "Telegram Configuration"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('Ticket', 'Ticket'),
        ('Task', 'Project Task'),
        ('System', 'System Alert'),
        ('Maintenance', 'Maintenance'),
    ]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True, help_text="Link to the event (e.g. /tickets/1/)")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='System')

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
