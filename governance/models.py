from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count

# A. Annual Plan & Budgeting
class FiscalYear(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Approved', 'Approved'),
        ('Closed', 'Closed'),
    ]
    year = models.IntegerField(unique=True)
    total_budget = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')

    def __str__(self):
        return str(self.year)

class BudgetPost(models.Model):
    CATEGORY_CHOICES = [
        ('Hardware', 'Hardware'),
        ('Software', 'Software'),
        ('License', 'License'),
        ('Service', 'Service'),
        ('Project', 'Project'),
    ]
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name='budget_posts')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    department = models.ForeignKey('assets.Department', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey('assets.Location', on_delete=models.SET_NULL, null=True, blank=True)
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.fiscal_year.year})"

# B. IT Development (Projects)
# B. IT Projects
class Project(models.Model):
    STATUS_CHOICES = [
        ('Planning', 'Planning'),
        ('In Progress', 'In Progress'),
        ('On Hold', 'On Hold'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    name = models.CharField(max_length=200)
    description = models.TextField()
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='managed_projects')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Planning')
    progress = models.IntegerField(default=0, help_text="0-100%")

    def __str__(self):
        return self.name

class ProjectTask(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    name = models.CharField(max_length=200)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    @property
    def is_past_due(self):
        return self.status != 'Completed' and self.due_date and self.due_date < timezone.now().date()

    def __str__(self):
        return f"{self.project.name} - {self.name}"

# C. Daily Logs
class RoutineTask(models.Model):
    CATEGORY_CHOICES = [
        ('Network', 'Network'),
        ('Server', 'Server'),
        ('Support', 'Support'),
        ('Development', 'Development'),
    ]
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    frequency = models.CharField(max_length=50, help_text="Daily, Weekly, Monthly", default='Daily')

    def __str__(self):
        return f"{self.name} ({self.category})"

class DailyLog(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved', 'Approved'),
    ]
    SHIFT_CHOICES = [
        ('Morning', 'Morning'),
        ('Afternoon', 'Afternoon'),
        ('Night', 'Night'),
        ('Full Day', 'Full Day'),
    ]
    LOCATION_CHOICES = [
        ('HO', 'Head Office'),
        ('SITE', 'On-Site / Visit'),
        ('REMOTE', 'Remote / WFH'),
    ]
    # Revert: Add defaults to avoid interactive migration prompt
    executor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    date = models.DateField(default=timezone.now)
    shift = models.CharField(max_length=50, choices=SHIFT_CHOICES, default="Morning")
    work_location = models.CharField(max_length=10, choices=LOCATION_CHOICES, default='HO')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    note = models.TextField(blank=True, help_text="General summary of the day")
    
    class Meta:
        unique_together = ('executor', 'date')

    def __str__(self):
        username = self.executor.username if self.executor else "Unknown"
        return f"{self.date} - {username}"

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class DailyLogItem(models.Model):
    STATUS_CHOICES = [
        ('Before', 'Before'), # Legacy support if needed, or just new
        ('Completed', 'Completed'),
        ('In Progress', 'In Progress'),
    ]
    CATEGORY_CHOICES = [
        ('Network', 'Network'),
        ('Server', 'Server'),
        ('Support', 'Support'),
        ('Development', 'Development'),
        ('Meeting', 'Meeting'),
        ('Other', 'Other'),
    ]
    log = models.ForeignKey(DailyLog, on_delete=models.CASCADE, related_name='items')
    
    # Improved Manual Fields
    task_name = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    
    # Optional Relations to Assets/Infra (Explicit)
    related_asset = models.ForeignKey('assets.Asset', on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_log_items')
    related_infra = models.ForeignKey('assets.Infrastructure', on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_log_items')

    # Keep Legacy Generic Relations for Signals/Auto-log (Ticket/Maintenance)
    # We can hide this from the manual form but keep it for the system.
    task = models.ForeignKey(RoutineTask, on_delete=models.CASCADE, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Completed')
    note = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        # Auto-fill task_name if linked to routine task or generic object
        if not self.task_name:
            if self.task:
                self.task_name = self.task.name
            elif self.content_object:
                self.task_name = str(self.content_object)
        
        # Auto-fill category if linked
        if self.category == 'Other':
             if self.task:
                 self.category = self.task.category
             elif self.content_object and hasattr(self.content_object, 'category'):
                 # Attempt to map or just use text if it matches choices?
                 # For now, let's leave it as explicit manual override or default.
                 pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.log} - {self.task_name or 'Activity'}"

class MonthlyReport(models.Model):
    period_date = models.DateField(help_text="Select the 1st of the month")
    generated_at = models.DateTimeField(auto_now=True)
    
    total_tickets = models.IntegerField(default=0)
    resolved_tickets = models.IntegerField(default=0)
    avg_resolution_hours = models.FloatField(default=0.0)
    sla_compliance_rate = models.FloatField(default=0.0, help_text="Percentage 0-100")
    top_technician = models.CharField(max_length=200, blank=True)
    most_common_issue = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True, help_text="Manager's analysis")

    def generate_data(self):
        from tickets.models import Ticket
        
        # Filter tickets created in the selected month
        queryset = Ticket.objects.filter(
            created_at__year=self.period_date.year,
            created_at__month=self.period_date.month
        )
        
        self.total_tickets = queryset.count()
        
        resolved_qs = queryset.filter(status__in=['Resolved', 'Closed'])
        self.resolved_tickets = resolved_qs.count()
        
        # Calculate Averages & SLA
        total_seconds = 0
        resolved_count_for_avg = 0
        sla_met_count = 0
        
        for t in resolved_qs:
            # Determine end time
            end_time = t.resolved_at or t.closed_at or timezone.now()
            
            # Duration
            duration = end_time - t.created_at
            total_seconds += duration.total_seconds()
            resolved_count_for_avg += 1
            
            # SLA Check
            if t.due_date:
                if end_time <= t.due_date:
                    sla_met_count += 1
            else:
                sla_met_count += 1 # Assume met if no due date

        if resolved_count_for_avg > 0:
            self.avg_resolution_hours = round((total_seconds / 3600) / resolved_count_for_avg, 2)
            self.sla_compliance_rate = round((sla_met_count / resolved_count_for_avg) * 100, 2)
        else:
            self.avg_resolution_hours = 0.0
            self.sla_compliance_rate = 100.0
            
        # Top Technician
        top_tech = queryset.exclude(assigned_to=None).values('assigned_to__username').annotate(count=Count('id')).order_by('-count').first()
        if top_tech:
            self.top_technician = f"{top_tech['assigned_to__username']} ({top_tech['count']})"
        else:
            self.top_technician = "None"
            
        # Most Common Issue (Category)
        top_cat = queryset.values('category').annotate(count=Count('id')).order_by('-count').first()
        if top_cat:
            self.most_common_issue = f"{top_cat['category']} ({top_cat['count']})"
        else:
            self.most_common_issue = "None"
            
        self.save()

    def save(self, *args, **kwargs):
        # Auto-generate on first save if manual creation, 
        # but usually triggered via admin action / method.
        # We won't force generation on save to allow manual edits if needed, 
        # but typically this is called explicitly.
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Report: {self.period_date.strftime('%B %Y')}"
