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
            
        super().save(*args, **kwargs)

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
