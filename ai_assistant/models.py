from django.db import models
from django.conf import settings

class AIConfiguration(models.Model):
    base_url = models.URLField(
        default="http://192.168.0.14:8080/v1", 
        help_text="Base URL for the OpenAI compatible API (e.g., http://192.168.0.14:8080/v1)"
    )
    api_key = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="API Key (Leave blank if not required by local AI, e.g. LM Studio or Ollama)"
    )
    model_name = models.CharField(
        max_length=100, 
        default="local-model",
        help_text="Model name to use (often ignored by local models, but required by API format)"
    )
    system_prompt = models.TextField(
        default="You are a helpful IT Support Assistant for the ITMS Pro system. Keep your answers clear, technical but easy to understand, and polite.",
        help_text="Instructions to define the assistant's behavior and personality."
    )
    is_active = models.BooleanField(
        default=True, 
        help_text="Only the active configuration will be used."
    )
    
    class Meta:
        verbose_name = "AI Configuration"
        verbose_name_plural = "AI Configurations"

    def save(self, *args, **kwargs):
        # Ensure only one configuration is active at a time
        if self.is_active:
            AIConfiguration.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"AI Config: {self.base_url} ({self.model_name})"


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_chat_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Session {self.id} for {self.user.username}"


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('system', 'System'),
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.get_role_display()} at {self.timestamp}"


class AIDataSkill(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., Check Old Assets")
    description = models.TextField(blank=True, help_text="Describe what this skill does.")
    trigger_keywords = models.TextField(help_text="Comma-separated keywords to trigger this query (e.g., 'aset lama, diatas 5 tahun').")
    sql_query = models.TextField(help_text="Read-Only SQL Query (e.g., SELECT name, status FROM assets_asset WHERE ...). DO NOT use DELETE/UPDATE.")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "AI Data Skill"
        verbose_name_plural = "AI Data Skills"

    def __str__(self):
        return self.name
