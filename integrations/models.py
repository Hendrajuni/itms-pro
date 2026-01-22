from django.db import models

class WhatsAppConfig(models.Model):
    api_url = models.CharField(
        max_length=255, 
        default='https://api.fonnte.com/send',
        help_text="API Endpoint URL (e.g. Fonnte, Twilio)"
    )
    api_token = models.CharField(max_length=255, help_text="API Authorization Token")
    default_target_number = models.CharField(
        max_length=50, 
        help_text="Default number for admin alerts (e.g. 62812xxxx)",
        blank=True, null=True
    )
    is_active = models.BooleanField(default=True, verbose_name="Enable WhatsApp Notifications")

    class Meta:
        verbose_name = "WhatsApp Configuration"
        verbose_name_plural = "WhatsApp Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(WhatsAppConfig, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "WhatsApp Settings"


class TelegramConfig(models.Model):
    bot_token = models.CharField(max_length=255, help_text="Telegram Bot Token")
    chat_id = models.CharField(max_length=100, help_text="Default Chat ID / Group ID")
    is_active = models.BooleanField(default=True, verbose_name="Enable Telegram Notifications")

    class Meta:
        verbose_name = "Telegram Configuration"
        verbose_name_plural = "Telegram Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(TelegramConfig, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Telegram Settings"


class EmailConfig(models.Model):
    smtp_host = models.CharField(max_length=255, help_text="SMTP Server Host (e.g. smtp.gmail.com)")
    smtp_port = models.IntegerField(default=587, help_text="SMTP Port (e.g. 587)")
    smtp_user = models.CharField(max_length=255, help_text="SMTP User / Email Address")
    smtp_password = models.CharField(max_length=255, help_text="SMTP Password / App Password")
    use_tls = models.BooleanField(default=True, verbose_name="Use TLS")
    default_from_email = models.CharField(max_length=255, help_text="Default 'From' Email Address", default="noreply@example.com")
    is_active = models.BooleanField(default=True, verbose_name="Enable Email Notifications")

    class Meta:
        verbose_name = "Email Configuration (SMTP)"
        verbose_name_plural = "Email Configuration (SMTP)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(EmailConfig, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Email Settings"
