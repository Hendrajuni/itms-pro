from django.contrib import admin
from .models import AIConfiguration, ChatSession, ChatMessage, AIDataSkill

@admin.register(AIConfiguration)
class AIConfigurationAdmin(admin.ModelAdmin):
    list_display = ('base_url', 'model_name', 'is_active')
    list_filter = ('is_active',)

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'timestamp')
    can_delete = False

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    inlines = [ChatMessageInline]
    readonly_fields = ('user', 'created_at')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'role', 'timestamp')
    list_filter = ('role', 'timestamp')
    search_fields = ('content',)
    readonly_fields = ('session', 'role', 'content', 'timestamp')

@admin.register(AIDataSkill)
class AIDataSkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'trigger_keywords')
    list_filter = ('is_active',)
    search_fields = ('name', 'trigger_keywords')
