from django.db import models
from django.conf import settings
from assets.models import Asset
from datetime import date, timedelta
from django.utils import timezone

PRIORITY_CHOICES = [
    ('Low', 'Low'),
    ('Medium', 'Medium'),
    ('High', 'High'),
    ('Critical', 'Critical'),
]

STATUS_CHOICES = [
    ('Open', 'Open'),
    ('Assigned', 'Assigned'),
    ('In_Progress', 'In Progress'),
    ('Pending_Vendor', 'Pending Vendor'),
    ('Resolved', 'Resolved'),
    ('Closed', 'Closed'),
]

CATEGORY_CHOICES = [
    ('Hardware', 'Hardware'),
    ('Software', 'Software'),
    ('Network', 'Network'),
    ('Access_Request', 'Access Request'),
    ('Daily_Check_Fail', 'Daily Check Fail'),
    ('Other', 'Other'),
]

class TicketTopic(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name}"

from simple_history.models import HistoricalRecords

class Ticket(models.Model):
    history = HistoricalRecords()
    ticket_code = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets_created')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_assigned')
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    
    topic = models.ForeignKey(TicketTopic, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    attachment = models.FileField(upload_to='tickets/attachments/', blank=True, null=True)
    
    # SLA & Tracking
    resolved_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True, help_text="1=Poor, 5=Excellent")
    feedback = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = not self.pk
        
        # 1. Auto-fill from Topic
        if self.topic:
            if not self.title:
                self.title = self.topic.name
            if self.priority == 'Medium':
                self.priority = self.topic.priority

        # 2. Generate Ticket Code
        if not self.ticket_code:
            current_year = date.today().year
            last_ticket = Ticket.objects.filter(ticket_code__contains=f"TCK-{current_year}-").order_by('id').last()
            if last_ticket:
                try:
                    last_seq = int(last_ticket.ticket_code.split('-')[-1])
                    new_seq = last_seq + 1
                except (IndexError, ValueError):
                    new_seq = 1
            else:
                new_seq = 1
            self.ticket_code = f"TCK-{current_year}-{new_seq:04d}"

        # 3. SLA Logic (Set Due Date on Creation)
        if is_new and not self.due_date:
            now = timezone.now()
            if self.priority == 'Critical':
                self.due_date = now + timedelta(hours=4)
            elif self.priority == 'High':
                self.due_date = now + timedelta(hours=24) # 1 day
            elif self.priority == 'Medium':
                self.due_date = now + timedelta(days=3)
            elif self.priority == 'Low':
                self.due_date = now + timedelta(days=7)

        # 4. Status Workflow Logic
        now = timezone.now()
        
        # Resolved
        if self.status == 'Resolved' and not self.resolved_at:
            self.resolved_at = now
            
        # Closed
        if self.status == 'Closed' and not self.closed_at:
            self.closed_at = now

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_code} - {self.title}"

class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to='tickets/comments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.ticket.ticket_code}"
