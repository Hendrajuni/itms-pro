from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from import_export.admin import ImportExportModelAdmin
from .models import FiscalYear, BudgetPost, Project, ProjectTask, DailyLog, DailyLogItem, RoutineTask, MonthlyReport, DisposalRequest

# A. Budgeting
class BudgetPostInline(admin.TabularInline):
    model = BudgetPost
    extra = 1

@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'total_budget', 'status')
    inlines = [BudgetPostInline]

# B. Projects
class ProjectTaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 1

@admin.register(Project)
class ProjectAdmin(ImportExportModelAdmin):
    list_display = ('name', 'manager', 'start_date', 'end_date', 'status', 'progress')
    list_filter = ('status', 'manager')
    search_fields = ('name', 'description')
    inlines = [ProjectTaskInline]

# C. Daily Logs
class DailyLogItemInline(admin.TabularInline):
    model = DailyLogItem
    extra = 1

@admin.register(DailyLogItem)
class DailyLogItemAdmin(ImportExportModelAdmin):
    list_display = ('get_date', 'get_executor', 'get_task_info', 'get_category_styled', 'get_status_styled', 'get_asset_display', 'get_infrastructure_display', 'start_time', 'end_time')
    list_filter = ('log__date', 'status', 'task__category', 'log__executor')
    search_fields = ('task__name', 'note', 'log__executor__username', 'log__executor__first_name')
    autocomplete_fields = ['log', 'task']
    date_hierarchy = 'log__date'
    
    def get_task_info(self, obj):
        if obj.task:
             return obj.task.name
        if obj.content_object:
             return str(obj.content_object)
        return obj.note[:50] if obj.note else "Ad-hoc"
    get_task_info.short_description = 'Task / Activity'

    def get_date(self, obj):
        return obj.log.date
    get_date.admin_order_field = 'log__date'
    get_date.short_description = 'Date'

    def get_executor(self, obj):
        return obj.log.executor
    get_executor.admin_order_field = 'log__executor'
    get_executor.short_description = 'User'

    def get_category_styled(self, obj):
        category = "Ad-hoc"
        if obj.task:
            category = obj.task.category
        elif obj.content_object:
             if hasattr(obj.content_object, 'category'):
                 category = getattr(obj.content_object, 'category', 'Ad-hoc')
             elif hasattr(obj.content_object, 'maintenance_type'):
                 category = getattr(obj.content_object, 'maintenance_type', 'Ad-hoc')
        
        # Style logic
        color = 'secondary'
        # Normalize for case-insensitive matching
        cat_lower = str(category).lower()
        
        if any(x in cat_lower for x in ['network', 'server', 'corrective']):
            color = 'info'
        elif any(x in cat_lower for x in ['hardware', 'asset', 'preventive']):
            color = 'primary'
        elif any(x in cat_lower for x in ['software', 'application', 'upgrade']):
            color = 'success'
        elif any(x in cat_lower for x in ['critical', 'issue', 'repair']):
            color = 'danger'
        elif any(x in cat_lower for x in ['other', 'ad-hoc']):
            color = 'secondary'
            
        return format_html('<span class="badge" style="background-color: var(--bs-{}); text-transform: uppercase;">{}</span>', color, category)
    get_category_styled.short_description = 'Category'
    get_category_styled.admin_order_field = 'task__category'

    def get_status_styled(self, obj):
        # Prefer status from linked object if available
        status = obj.status
        if obj.content_object and hasattr(obj.content_object, 'status'):
            status = obj.content_object.status

        # Style logic
        color = 'secondary'
        status_lower = str(status).lower().replace('_', ' ')
        
        if status_lower in ['fixed', 'ok', 'completed', 'resolved', 'closed']:
            color = 'success'
        elif status_lower in ['pending', 'open', 'in progress', 'assigned', 'scheduled', 'pending vendor']:
            color = 'warning'
        elif status_lower in ['broken', 'issue', 'critical', 'cancelled']:
            color = 'danger'
            
        return format_html('<span class="badge" style="background-color: var(--bs-{});">{}</span>', color, status)
    get_status_styled.short_description = 'Status'
    get_status_styled.admin_order_field = 'status'

    def get_asset_display(self, obj):
        if obj.content_object:
            # Check for AssetMaintenance
            asset = None
            if hasattr(obj.content_object, 'asset'):
                asset = obj.content_object.asset
            # Check if it IS an asset
            elif hasattr(obj.content_object, 'model') and 'Asset' in str(type(obj.content_object)):
                 asset = obj.content_object
            
            if asset:
                url = reverse('admin:assets_asset_change', args=[asset.pk])
                return format_html('<a href="{}">{}</a>', url, asset.name)
        return "-"
    get_asset_display.short_description = "Asset"
    get_asset_display.admin_order_field = 'content_type' # Approximation

    def get_infrastructure_display(self, obj):
        if obj.content_object:
             # Check for InfraMaintenance
            if hasattr(obj.content_object, 'infrastructure'):
                infra = obj.content_object.infrastructure
                url = reverse('admin:assets_infrastructure_change', args=[infra.pk])
                return format_html('<a href="{}">{}</a>', url, infra.name)
        return "-"
    get_infrastructure_display.short_description = "Infrastructure"

@admin.register(DailyLog)
class DailyLogAdmin(ImportExportModelAdmin):
    list_display = ('date', 'executor', 'shift', 'status')
    list_filter = ('date', 'executor', 'status')
    search_fields = ('executor__username', 'executor__first_name')
    inlines = [DailyLogItemInline]

@admin.register(RoutineTask)
class RoutineTaskAdmin(ImportExportModelAdmin):
    list_display = ('name', 'category', 'frequency')
    list_filter = ('category', 'frequency')
    search_fields = ('name',)

# D. Reports
@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('period_date', 'total_tickets', 'resolved_tickets', 'sla_compliance_rate', 'generated_at')
    readonly_fields = ('generated_at', 'total_tickets', 'resolved_tickets', 'avg_resolution_hours', 'sla_compliance_rate', 'top_technician', 'most_common_issue')
    actions = ['recalculate_data']

    def recalculate_data(self, request, queryset):
        count = 0
        for report in queryset:
            report.generate_data()
            count += 1
        self.message_user(request, f"{count} reports recalculated.", messages.SUCCESS)
    recalculate_data.short_description = "Recalculate Statistics"

@admin.register(DisposalRequest)
class DisposalRequestAdmin(admin.ModelAdmin):
    list_display = ('asset', 'requested_by', 'request_date', 'status', 'approved_by')
    list_filter = ('status', 'method')
    search_fields = ('asset__asset_code', 'asset__name', 'reason')
    readonly_fields = ('request_date', 'approval_date')

