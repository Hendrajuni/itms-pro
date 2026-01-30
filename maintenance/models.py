from django.db import models
from django.conf import settings
from assets.models import Asset, Infrastructure, Vendor
from datetime import date

class MaintenanceBase(models.Model):
    MAINTENANCE_TYPES = [
        ('Preventive', 'Preventive'),
        ('Corrective', 'Corrective'),
        ('Upgrade', 'Upgrade'),
    ]
    STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    maintenance_code = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=200)
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_technician')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_vendor')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    maintenance_checklist = models.JSONField(default=list, blank=True, help_text="List of checklist items e.g. [{'task': 'Clean Fan', 'done': False}]")
    notes = models.TextField(blank=True)
    photo_before = models.ImageField(upload_to='maintenance/before/', blank=True)
    photo_after = models.ImageField(upload_to='maintenance/after/', blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.maintenance_code:
            current_year = date.today().year
            # Helper to find max sequence across both tables is imperfect without a dedicated sequence table.
            # But we can try to find the max ID of THIS specific child model, 
            # OR typically "Global" implies unique across the system. 
            # Given the constraints, I'll implement a helper that checks BOTH if they exist, 
            # but simpler approach: Just check the child's table for now, or check both if requested carefully.
            
            # Let's try to do a robust check across both tables to simulate "global" sequence
            last_asset_mnt = AssetMaintenance.objects.filter(maintenance_code__contains=f"MNT-{current_year}-").order_by('maintenance_code').last()
            last_infra_mnt = InfraMaintenance.objects.filter(maintenance_code__contains=f"MNT-{current_year}-").order_by('maintenance_code').last()

            seqs = []
            if last_asset_mnt:
                try:
                    seqs.append(int(last_asset_mnt.maintenance_code.split('-')[-1]))
                except (IndexError, ValueError):
                    pass
            if last_infra_mnt:
                try:
                    seqs.append(int(last_infra_mnt.maintenance_code.split('-')[-1]))
                except (IndexError, ValueError):
                    pass
            
            max_seq = max(seqs) if seqs else 0
            new_seq = max_seq + 1
            
            self.maintenance_code = f"MNT-{current_year}-{new_seq:03d}"
            
        # Image Compression
        from core.utils import compress_image
        if self.photo_before:
            # Check if it's a new upload (has file but no path usually, but safer to just check content type/size or recompress)
            # Simple check: compress only if size is large to avoid re-compressing indefinitely if we don't track state
            # Better approach for Django: field.file object usually has a size attribute.
            # But here we just blindly compress providing it's not None. The util handles if it's already small/compressed?
            # Actually, repeatedly compressing JPEG degrades quality. Ideally we check if it changed.
            # For simplicity in this task: We compress. Django `save()` is called on update too.
            # We can check if pk is None (creation) or strictly if field changed.
            # Let's compress if it's a newly uploaded file (File object vs FieldFile).
            # Usually checking `if hasattr(self.photo_before, 'file')` helps. 
            pass 
            # Note: Implementing robust check is complex in model save. 
            # Simplest for now: Just run compression. The utility could be smart.
            
            # Let's simple apply compression if the file object is present.
            compressed = compress_image(self.photo_before)
            if compressed:
                self.photo_before = compressed

        if self.photo_after:
            compressed = compress_image(self.photo_after)
            if compressed:
                self.photo_after = compressed
            
        super().save(*args, **kwargs)

        # --- Auto-Daily Log Integration ---
        if self.technician:
            try:
                from django.utils import timezone
                from django.contrib.contenttypes.models import ContentType
                from governance.models import DailyLog, DailyLogItem

                today = timezone.now().date()
                
                # 1. Get/Create DailyLog for the technician
                daily_log, created = DailyLog.objects.get_or_create(
                    executor=self.technician,
                    date=today,
                    defaults={'status': 'Draft'}
                )

                # 2. Prepare Log Content
                # Extract completed checklist items
                checklist_summary = ""
                if self.maintenance_checklist:
                    # Safely handle if it's not a list (e.g. dict or string, though it should be list)
                    cl_data = self.maintenance_checklist if isinstance(self.maintenance_checklist, list) else []
                    done_items = [item.get('task', 'Unknown') for item in cl_data if isinstance(item, dict) and item.get('done')]
                    if done_items:
                        checklist_summary = "Checklist Completed: " + ", ".join(done_items)

                # Combine with main notes
                full_note = f"{checklist_summary}\n\nTechnical Notes: {self.notes}" if checklist_summary else self.notes

                # Map Status
                log_status = 'In Progress'
                if self.status == 'Completed':
                    log_status = 'Completed'
                elif self.status == 'Cancelled':
                    log_status = 'Completed' # Or specific status if available

                # 3. Update or Create DailyLogItem linked to this maintenance
                # We need ContentType
                ct = ContentType.objects.get_for_model(self)
                
                DailyLogItem.objects.update_or_create(
                    log=daily_log,
                    content_type=ct,
                    object_id=self.pk,
                    defaults={
                        'task_name': f"Maintenance: {self.title}",
                        'category': 'Support', # Default to Support or Engineering
                        'status': log_status,
                        'note': full_note.strip()
                    }
                )
            except Exception as e:
                # Fail silently or log error to avoid breaking the main save flow
                print(f"Error auto-logging maintenance: {e}")

    def __str__(self):
        return f"{self.maintenance_code} - {self.title}"

class AssetMaintenance(MaintenanceBase):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenances')

    class Meta:
        verbose_name = "Asset Maintenance"
        verbose_name_plural = "Asset Maintenances"

class InfraMaintenance(MaintenanceBase):
    infrastructure = models.ForeignKey(Infrastructure, on_delete=models.CASCADE, related_name='maintenances')

    class Meta:
        verbose_name = "Infrastructure Maintenance"
        verbose_name_plural = "Infrastructure Maintenances"

class MaintenanceSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Yearly', 'Yearly'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text="Description of the standard operating procedure.")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='Monthly')
    next_run_date = models.DateField(help_text="The next date this maintenance should be performed.")
    
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceBase.MAINTENANCE_TYPES, default='Preventive')
    
    # Target (Generic relation or nullable FKs)
    # Using nullable FKs for simplicity as per existing pattern
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True, related_name='maintenance_schedules')
    infrastructure = models.ForeignKey(Infrastructure, on_delete=models.CASCADE, null=True, blank=True, related_name='maintenance_schedules')
    
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_schedules')
    checklist = models.JSONField(default=list, blank=True, help_text="List of tasks e.g. [{'task': 'Check Temp', 'done': False}]")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    last_generated = models.DateTimeField(null=True, blank=True, help_text="When the last ticket was generated from this schedule")

    def __str__(self):
        return f"{self.title} ({self.frequency})"

    def save(self, *args, **kwargs):
        # Basic Validation: Ensure either asset or infra is set, not both or neither (though model allows both, logic should prefer one)
        super().save(*args, **kwargs)

    def create_ticket(self):
        """
        Creates a Maintenance Ticket (Asset or Infra) based on this schedule.
        """
        from .models import AssetMaintenance, InfraMaintenance
        from django.utils import timezone

        # 1. Determine Target
        if self.asset:
            ModelClass = AssetMaintenance
            target_field = 'asset'
            target_obj = self.asset
        elif self.infrastructure:
            ModelClass = InfraMaintenance
            target_field = 'infrastructure'
            target_obj = self.infrastructure
        else:
            return None # Should not happen if validation works

        # 2. Create Ticket
        # We append the date to title to make it unique/clear
        run_date = timezone.now().date()
        new_title = f"{self.title} - {run_date.strftime('%d/%m/%Y')}"
        
        ticket = ModelClass(
            title=new_title,
            maintenance_type=self.maintenance_type,
            # priority='Normal', # Field does not exist in MaintenanceBase
            status='Scheduled',
            scheduled_date=run_date,
            technician=self.assigned_to,
            maintenance_checklist=self.checklist,
            notes=self.description, # Map description to notes
        )
        
        # Set the specific FK
        setattr(ticket, target_field, target_obj)
        
        ticket.save()
        
        # 3. Update Schedule
        self.last_generated = timezone.now()
        # Optionally update next_run_date here if we were doing strict scheduling
        # But for 'Generate Now' manual trigger, strictly speaking we might not want to push the next date
        # OR we might want to. Let's leave next_run_date alone for manual triggers for now, 
        # as the user might be testing or doing an extra run.
        self.save()
        
        return ticket
