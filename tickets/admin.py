from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Ticket, TicketComment, TicketTopic

class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 1

@admin.register(TicketTopic)
class TicketTopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'priority', 'is_active')
    list_filter = ('category', 'priority', 'is_active')
    search_fields = ('name',)

@admin.register(Ticket)
class TicketAdmin(ImportExportModelAdmin):
    list_display = ('ticket_code', 'topic', 'priority', 'status', 'assigned_to', 'due_date', 'is_overdue')
    list_filter = ('status', 'priority', 'category', 'topic')
    search_fields = ('ticket_code', 'topic__name', 'description', 'created_by__username')
    readonly_fields = ('ticket_code', 'created_at', 'updated_at', 'resolved_at', 'closed_at', 'due_date')
    exclude = ('title',)
    fields = ('ticket_code', 'topic', 'description', 'priority', 'status', 'category', 'assigned_to', 'asset', 'attachment', 'created_by', 'due_date', 'resolved_at', 'closed_at', 'created_at', 'updated_at')
    inlines = [TicketCommentInline]

    def is_overdue(self, obj):
        from django.utils import timezone
        # If not closed/resolved and past due date
        if obj.status not in ['Resolved', 'Closed'] and obj.due_date and timezone.now() > obj.due_date:
            return True
        return False
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue?'

@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('ticket__ticket_code', 'message')
