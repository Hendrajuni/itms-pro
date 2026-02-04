from django.db import models
from django.contrib.auth.models import AbstractUser

from simple_history.models import HistoricalRecords

class CustomUser(AbstractUser):
    history = HistoricalRecords()
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.ForeignKey('assets.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    location = models.ForeignKey('assets.Location', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    
    # Employee Profile
    job_title = models.CharField(max_length=100, blank=True, help_text="Official Job Title, e.g., Senior Accountant")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    EMPLOYEE_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PROBATION', 'Probation'),
        ('CONTRACT', 'Contract'),
        ('RESIGNED', 'Resigned'),
    ]
    employee_status = models.CharField(max_length=20, choices=EMPLOYEE_STATUS_CHOICES, default='ACTIVE')
    
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to='users/photos/', blank=True)

    def __str__(self):
        return self.username


class SiteSetting(models.Model):
    site_name = models.CharField(max_length=100, default="ITMS Pro")
    
    # Company Identity
    company_name = models.CharField(max_length=100, default="PT. PMG - PROPERTY", help_text="Used in Reports")
    company_address = models.TextField(blank=True, help_text="Full address for report headers")
    company_phone = models.CharField(max_length=50, blank=True)
    company_email = models.EmailField(blank=True)
    
    # Application Settings
    asset_id_prefix = models.CharField(max_length=10, default="PMG", help_text="Prefix for auto-generated Asset IDs (e.g. PMG-0001)")
    
    logo = models.ImageField(upload_to='branding/', default='img/default_logo.png')
    favicon = models.ImageField(upload_to='branding/', null=True, blank=True)
    login_background = models.ImageField(upload_to='branding/', null=True, blank=True)
    maintenance_mode = models.BooleanField(default=False)

    # License / Edition Control (Obfuscated)
    # Default is ESSENTIAL (d41d8cd98f00b204e9800998ecf8427e - MD5 of empty)
    # ENTERPRISE is (e10adc3949ba59abbe56e057f20f883e - MD5 of 123456)
    activation_code = models.CharField(max_length=255, default='d41d8cd98f00b204e9800998ecf8427e', help_text="System License Hash")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Site Configuration"

class PersonalNote(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='personal_notes')
    content = models.TextField(blank=True, help_text="Raw text content or JSON if checklist")
    is_checklist = models.BooleanField(default=False)
    checklist_data = models.JSONField(default=list, blank=True, help_text="e.g. [{'task': 'Buy Milk', 'done': False}]")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Personal Note"
        verbose_name_plural = "Personal Notes"

    def __str__(self):
        return f"Note for {self.user.username}"
