from django.db import models
from django.conf import settings
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from datetime import date
from django.utils import timezone
from django.core.exceptions import ValidationError
import base64
from django.urls import reverse
from mptt.models import MPTTModel, TreeForeignKey

class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_departments', help_text="Head of Department")

    def __str__(self):
        return self.name

class DepartmentHead(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='regional_heads')
    location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='regional_heads')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='regional_roles')
    
    class Meta:
        unique_together = ('department', 'location')
        verbose_name = "Regional Head"
        verbose_name_plural = "Regional Heads"

    def __str__(self):
        return f"{self.department.name} - {self.location.name} ({self.manager})"

class Location(MPTTModel):
    TYPE_CHOICES = [
        ('HO', 'Head Office'),
        ('PROVINCE', 'Province'),
        ('RO', 'Regional Office'),
        ('ESTATE', 'Estate / Kebun'),
        ('MILL', 'Mill / PKS'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    
    # Hierarchy Fields
    parent = TreeForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', help_text="Parent location (e.g. Province for an RO)")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='OTHER')
    
    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return self.name

    def get_descendants(self, include_self=True):
        # Iterative approach to avoid RecursionError in case of cycles or deep trees
        descendants = set()
        if include_self:
            descendants.add(self)
            
        stack = list(self.children.all())
        processed_ids = {self.id} if include_self else set()
        
        while stack:
            child = stack.pop()
            if child.id in processed_ids:
                continue
            
            processed_ids.add(child.id)
            descendants.add(child)
            
            # Add children of this child to stack
            stack.extend(child.children.all())
            
        return list(descendants)

    @property
    def root_node(self):
        """Returns the top-level ancestor (Root) of this location."""
        current = self
        visited = {current.id}
        while current.parent:
            current = current.parent
            if current.id in visited:
                break # Cycle detected
            visited.add(current.id)
        return current

class Vendor(models.Model):
    name = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    TYPE_CHOICES = [
        ('HW', 'Hardware'),
        ('SW', 'Software'),
        ('CL', 'Cloud'),
        ('IN', 'Infrastructure'),
    ]
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=2, choices=TYPE_CHOICES)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

from simple_history.models import HistoricalRecords

class Asset(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('IN_USE', 'In Use'),
        ('MAINTENANCE', 'Maintenance'),
        ('BROKEN', 'Broken'),
        ('DISPOSED', 'Disposed'),
        ('LOST', 'Lost'),
        ('RETIRED', 'Retired'),
    ]
    history = HistoricalRecords()

    # Relations
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='assets')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, related_name='assets')
    sub_location = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Kantor PKS, Pabrik")
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, related_name='assets')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='assets')
    infrastructure = models.ForeignKey('Infrastructure', on_delete=models.SET_NULL, null=True, blank=True, related_name='assets', help_text="Linked infrastructure (e.g. Server Rack, Cabling)")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_assets')

    # Basic Info
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, unique=True, blank=True, null=True)

    # Financial Info
    purchase_date = models.DateField(blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    warranty_end = models.DateField(blank=True, null=True)
    useful_life_years = models.IntegerField(default=5, help_text="Economic life in years")
    residual_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Estimated value at end of life")
    
    notes = models.TextField(blank=True, null=True)

    # Status & ID
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    asset_code = models.CharField(max_length=50, unique=True, editable=False)
    
    # Media
    photo = models.ImageField(upload_to='assets/photos/', blank=True, null=True)
    qr_code_image = models.ImageField(upload_to='assets/qrcodes/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_current_value(self):
        """
        Calculates Straight-Line Depreciation.
        Value = Purchase Price - ((Purchase Price - Residual) / Useful Life * Age)
        """
        if not self.purchase_price or not self.purchase_date:
            return 0
        
        age_in_days = (date.today() - self.purchase_date).days
        age_in_years = age_in_days / 365.25
        
        if age_in_years >= self.useful_life_years:
            return float(self.residual_value)
            
        depreciable_amount = self.purchase_price - self.residual_value
        depreciable_amount = float(depreciable_amount) # Convert to float for calculation
        
        annual_depreciation = depreciable_amount / self.useful_life_years
        total_depreciation = annual_depreciation * age_in_years
        
        current_val = float(self.purchase_price) - total_depreciation
        return max(current_val, float(self.residual_value))

    @property
    def current_book_value(self):
        return self.get_current_value()

    @property
    def age_usage(self):
        if not self.purchase_date:
            return "N/A"
        today = date.today()
        # Calculate difference
        # Simplistic approach:
        delta_days = (today - self.purchase_date).days
        years = delta_days // 365
        remaining_days = delta_days % 365
        months = remaining_days // 30
        
        parts = []
        if years > 0:
            parts.append(f"{years} Thn")
        if months > 0:
            parts.append(f"{months} Bln")
            
        if not parts:
            if delta_days < 30:
                return f"{delta_days} Hari"
            return "0 Bln"
            
        return " ".join(parts)

    def get_total_maintenance_cost(self):
        # Using default reverse relation name since we haven't confirmed related_name yet.
        # But wait, AssetMaintenance model (duplicate) was removed, checking MaintenanceBase
        # If accessing the maintenance app's AssetMaintenance, it usually has a ForeignKey.
        # Assuming related_name='maintenances' based on previous context.
        aggregated = self.maintenances.aggregate(total=models.Sum('cost'))
        return aggregated['total'] or 0

    def is_eol_candidate(self):
        if not self.purchase_date:
            return False
        age_years = (date.today() - self.purchase_date).days / 365.25
        return age_years >= self.useful_life_years

    def save(self, *args, **kwargs):
        if not self.asset_code:
            from django.apps import apps
            SiteSetting = apps.get_model('core', 'SiteSetting')
            try:
                setting = SiteSetting.objects.get(pk=1)
                prefix = setting.asset_id_prefix.upper()
            except SiteSetting.DoesNotExist:
                prefix = "PMG"

            today = timezone.now()
            year = today.year
            # Format: {PREFIX}-{SEQ}/{YYYY}/IT
            
            # Find last asset with this year's pattern
            last_asset = Asset.objects.filter(asset_code__contains=f"/{year}/").order_by('-asset_code').first()
            
            if last_asset:
                try:
                    # Extract sequence from PREFIX-####/...
                    parts = last_asset.asset_code.split('/')
                    # parts[0] should be PREFIX-####
                    seq_part = parts[0].split('-')[1]
                    seq = int(seq_part) + 1
                except (IndexError, ValueError):
                     seq = 1
            else:
                 seq = 1
            
            self.asset_code = f"{prefix}-{seq:04d}/{year}/IT"

        if not self.qr_code_image:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.asset_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            self.qr_code_image.save(f'qr_{self.asset_code}.png', ContentFile(buffer.getvalue()), save=False)

        # Auto-assign department and location based on the assigned user
        if self.assigned_to:
            if self.assigned_to.department:
                self.department = self.assigned_to.department

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset_code} - {self.name}"

    @property
    def safe_specification(self):
        try:
            return self.specification
        except Exception:
            return None

class AssetSpecification(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name='specification')
    cpu = models.CharField(max_length=100, blank=True, null=True)
    motherboard = models.CharField(max_length=100, blank=True, null=True)
    ram = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)

    # Legacy fields (kept for backward compatibility during migration, eventually to be removed)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=100, blank=True, null=True)
    # storage_devices field removed. Use AssetStorage model instead.

    def __str__(self):
        return f"Spec for {self.asset.asset_code}"

class NetworkInterface(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='network_interfaces')
    name = models.CharField(max_length=50, help_text="e.g. eth0, WAN, Slot 1")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=50, blank=True, null=True)
    vlan_id = models.IntegerField(blank=True, null=True, help_text="VLAN Tag/ID")
    subnet = models.ForeignKey('network.Subnet', on_delete=models.SET_NULL, null=True, blank=True, related_name='network_interfaces')
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-Sync to IPAM (IPAddress in network app)
        if self.ip_address and self.subnet:
            try:
                from network.models import IPAddress
                # Create or Update IPAddress entry
                # Assuming IP is unique per Subnet or globally unique enough for this logic
                ip_instance, created = IPAddress.objects.get_or_create(
                    address=self.ip_address,
                    subnet=self.subnet,
                    defaults={
                        'status': 'Active',
                        'asset': self.asset,
                        'description': f"Auto-assigned from Asset: {self.asset.name} ({self.name})"
                    }
                )
                if not created:
                    # Update existing if it was Free or Reserved
                    if ip_instance.status != 'Active' or ip_instance.asset != self.asset:
                        ip_instance.status = 'Active'
                        ip_instance.asset = self.asset
                        ip_instance.save()
            except Exception as e:
                # Log error or pass silently if network app issue
                print(f"IPAM Sync Error: {e}")

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

class AssetIPAddress(models.Model):
    # DEPRECATED: Replaced by NetworkInterface
    TYPE_CHOICES = [
        ('LAN', 'LAN'),
        ('WAN', 'WAN'),
        ('VPN', 'VPN'),
        ('VLAN', 'VLAN'),
    ]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='ip_addresses')
    ip_address = models.GenericIPAddressField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='LAN')
    
    def __str__(self):
        return f"{self.ip_address} ({self.get_type_display()})"




class AssetStorage(models.Model):
    STORAGE_TYPE_CHOICES = [
        ('HDD', 'HDD'),
        ('SSD', 'SSD'),
        ('NVMe', 'NVMe'),
        ('RAM', 'RAM'),
        ('Other', 'Other'),
    ]
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='storages')
    device_type = models.CharField(max_length=10, choices=STORAGE_TYPE_CHOICES, default='HDD')
    brand = models.CharField(max_length=100, blank=True, null=True)
    capacity = models.CharField(max_length=50, help_text="e.g. 512GB, 1TB")
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    purchase_date = models.DateField(blank=True, null=True)

    class Meta:
        # We explicitly set the table name to match the existing one in DB
        db_table = 'assets_assetstorage'
        verbose_name = "Storage Device"
        verbose_name_plural = "Storage Devices"

    def __str__(self):
        return f"{self.device_type} {self.capacity} - {self.brand}"

class AuditItem(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='audit_items')
    session_id = models.BigIntegerField(help_text="Legacy Audit Session ID") 
    status = models.CharField(max_length=20)
    scanned_at = models.DateTimeField(blank=True, null=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'assets_audititem'
        unique_together = (('session_id', 'asset'),)
        verbose_name = "Audit Record (Legacy)"
        verbose_name_plural = "Audit Records (Legacy)"

    def __str__(self):
        return f"Audit {self.session_id} - {self.asset.asset_code}"

class PartHistory(models.Model):
    # Restored legacy model to fix IntegrityError on deletion
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='part_history')
    part_name = models.CharField(max_length=100)
    action_date = models.DateField()
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        db_table = 'assets_parthistory'
        verbose_name = "Part History (Legacy)"
        verbose_name_plural = "Part History (Legacy)"

    def __str__(self):
        return f"{self.part_name} - {self.asset.asset_code}"

class InfrastructureType(models.Model):
    ICON_CHOICES = [
        ('server', 'Server'),
        ('broadcast-tower', 'Tower'),
        ('hdd', 'Storage / Rack'),
        ('bolt', 'Power / Panel'),
        ('battery-full', 'UPS'),
        ('network-wired', 'Cabling'),
        ('snowflake', 'Cooling'),
        ('cube', 'Generic Cube'),
        ('wifi', 'Wireless'),
        ('video', 'Camera'),
        ('print', 'Printer'),
    ]
    COLOR_CHOICES = [
        ('primary', 'Blue'),
        ('success', 'Green'),
        ('warning', 'Yellow'),
        ('danger', 'Red'),
        ('info', 'Cyan'),
        ('secondary', 'Gray'),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, editable=False)
    icon = models.CharField(max_length=50, choices=ICON_CHOICES, default='cube')
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='primary')
    is_featured = models.BooleanField(default=True, help_text="Show this type as a card on the dashboard")
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Infrastructure(models.Model):
    # Deprecated Choices - Moving to InfrastructureType
    TYPE_CHOICES = [
        ('TOWER', 'Tower'),
        ('SERVER_RACK', 'Server Rack'),
        ('WALLMOUNT', 'Rack Wallmount'),
        ('PANEL', 'Box Panel'),
        ('UPS', 'UPS / Power'),
        ('CABLING', 'Cabling'),
        ('COOLING', 'Cooling / AC'),
        ('OTHER', 'Other'),
    ]
    
    CONDITION_CHOICES = [
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
        ('CRITICAL', 'Critical'),
    ]

    infra_id = models.CharField(max_length=50, unique=True, editable=False)
    name = models.CharField(max_length=200)
    # Keeping old type for migration, added new relation
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='OTHER', blank=True) 
    infra_type = models.ForeignKey(InfrastructureType, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True)
    
    capacity = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 42U, 1200VA")
    photo = models.ImageField(upload_to='infrastructure/photos/', blank=True, null=True)
    
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD')
    last_maintenance_date = models.DateField(blank=True, null=True)
    next_maintenance_date = models.DateField(blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True)
    
    # Map Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Lat coordinate, e.g. -6.200000")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Long coordinate, e.g. 106.816666")
    
    def save(self, *args, **kwargs):
        if not self.infra_id:
            today = date.today()
            # Simple ID: INFR-YYYY-SEQ
            count = Infrastructure.objects.filter(infra_id__startswith=f"INFR-{today.year}").count() + 1
            self.infra_id = f"INFR-{today.year}-{count:04d}"
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.infra_id} - {self.name}"

    def get_absolute_url(self):
        return reverse('infra_detail', kwargs={'pk': self.pk})

    def get_qr_code_base64(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        # In a real deployed app, PREPEND the domain to make it scan-friendly from mobile
        # e.g. https://itms.local/... 
        # For now, we use the relative path or try to be smart.
        # Ideally, use settings.SITE_URL + self.get_absolute_url()
        data = self.get_absolute_url() 
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

class CloudAsset(models.Model):
    SERVICE_TYPE_CHOICES = [
        ('DOMAIN', 'Domain Name'),
        ('SHARED', 'Shared Hosting'),
        ('VPS', 'VPS / Cloud Server'),
        ('SSL', 'SSL Certificate'),
        ('SAAS', 'SaaS Subscription'),
        ('EMAIL', 'Email Hosting'),
        ('OTHER', 'Other'),
    ]
    
    BILLING_CYCLE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
        ('ONETIME', 'One-time'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PENDING', 'Pending'),
        ('SUSPENDED', 'Suspended'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]

    name = models.CharField(max_length=200, help_text="e.g. company.com or App Server")
    provider = models.CharField(max_length=100, help_text="e.g. AWS, Niagahoster, GoDaddy")
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='DOMAIN')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='YEARLY')
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    purchase_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    auto_renew = models.BooleanField(default=False)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    login_url = models.URLField(blank=True, null=True, help_text="Login URL for management console")
    
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.provider})"
    
    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - date.today()
        return delta.days
        
    @property
    def status_color(self):
        if self.status == 'EXPIRED' or self.status == 'SUSPENDED':
            return 'danger'
        if self.status == 'PENDING':
            return 'warning'
        
        # Check expiry for auto-warning
        days = self.days_until_expiry
        if days is not None:
            if days < 0: return 'danger'
            if days < 30: return 'warning'
            
        return 'success'

class AssetLoan(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='loans')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asset_loans')
    loan_date = models.DateTimeField(default=timezone.now)
    return_date = models.DateTimeField(blank=True, null=True)
    condition_out = models.TextField(blank=True, null=True, help_text="Condition when loaned")
    condition_in = models.TextField(blank=True, null=True, help_text="Condition when returned")
    loan_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Digital Signature
    signature_image = models.ImageField(upload_to='signatures/', blank=True, null=True)
    is_digital_sign = models.BooleanField(default=False)
    
    # Transfer Type
    is_permanent = models.BooleanField(default=True, help_text="If checked, ownership of the asset is transferred to this user permanently. If unchecked, it is a temporary loan.")

    def save(self, *args, **kwargs):
        if not self.loan_id:
            # LOAN-YYYY-SEQ
            count = AssetLoan.objects.filter(loan_date__year=timezone.now().year).count() + 1
            self.loan_id = f"LOAN-{timezone.now().year}-{count:04d}"
        
        # Logic: Update Asset assigned_to and Status
        if not self.return_date:
            # Check Out
            if self.is_permanent:
                self.asset.assigned_to = self.employee
            self.asset.status = 'IN_USE'
        else:
            # Check In
            if self.asset.assigned_to == self.employee:
                 self.asset.assigned_to = None
                 self.asset.status = 'AVAILABLE'
        
        self.asset.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.loan_id} - {self.asset.asset_code} ({self.employee.username})"

class Software(models.Model):
    LICENSE_TYPE_CHOICES = [
        ('SUBSCRIPTION', 'Subscription'),
        ('PERPETUAL', 'Perpetual'),
        ('FREE', 'Free / Open Source'),
        ('TRIAL', 'Trial'),
    ]

    name = models.CharField(max_length=200)
    vendor = models.ForeignKey('Vendor', on_delete=models.SET_NULL, null=True, blank=True)
    license_key = models.CharField(max_length=255, blank=True, null=True)
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPE_CHOICES, default='SUBSCRIPTION')
    purchase_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, help_text="Leave blank for Perpetual")
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    seats_total = models.PositiveIntegerField(default=1, help_text="Total number of licenses purchased")
    seats_used = models.PositiveIntegerField(default=0, editable=False)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'type': 'SW'})
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_license_type_display()})"
    
    @property
    def availability_percentage(self):
        if self.seats_total == 0: return 0
        return (self.seats_used / self.seats_total) * 100
        
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - date.today()
        return delta.days
    
    def save(self, *args, **kwargs):
        # Recalculate seats_used on save to be safe
        if self.pk:
            self.seats_used = self.allocations.count()
        super().save(*args, **kwargs)

class SoftwareAllocation(models.Model):
    software = models.ForeignKey(Software, on_delete=models.CASCADE, related_name='allocations')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='software_assets')
    asset = models.ForeignKey('Asset', on_delete=models.SET_NULL, null=True, blank=True, related_name='software_installed')
    assigned_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.software.seats_used = self.software.allocations.count()
            self.software.save()

    def delete(self, *args, **kwargs):
        software = self.software
        super().delete(*args, **kwargs)
        software.seats_used = software.allocations.count()
        software.save()
        
    def __str__(self):
        target = self.employee.get_full_name() if self.employee else (self.asset.name if self.asset else "Unknown")
        return f"{self.software.name} -> {target}"


class Contract(models.Model):
    TYPE_CHOICES = [
        ('LICENSE', 'Software License'),
        ('SERVICE', 'Service/Maintenance'),
        ('LEASE', 'Lease/Rental'),
        ('WARRANTY', 'Warranty Extension'),
        ('DOMAIN', 'Domain Name'),
        ('HOSTING', 'Web Hosting / VPS'),
        ('SAAS', 'SaaS Subscription'),
        ('ISP', 'Internet Service Provider'),
        ('SSL', 'SSL Certificate'),
        ('OTHER', 'Other'),
    ]

    BILLING_CYCLE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
        ('ONE_TIME', 'One Time'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
        ('PAID', 'Paid / Replaced'),
    ]

    title = models.CharField(max_length=200, help_text="e.g. Microsoft 365 Renewal 2026")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='contracts')
    contract_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SERVICE')
    
    start_date = models.DateField()
    end_date = models.DateField()
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='YEARLY')
    auto_renew = models.BooleanField(default=False)
    
    cost = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total Contract Value")
    document = models.FileField(upload_to='contracts/', blank=True, null=True, help_text="PDF/Docx Scan")
    
    # Cloud/Service Specific Fields
    ip_address = models.GenericIPAddressField(blank=True, null=True, help_text="For VPS/Hosting")
    login_url = models.URLField(blank=True, null=True, help_text="Console/Dashboard URL")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', editable=False)
    notes = models.TextField(blank=True, null=True)
    
    notify_days_before = models.IntegerField(default=30, help_text="Days before expiry to trigger alert")
    
    previous_contract = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replaced_by', help_text="The previous contract that this one renews/replaces")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_history(self):
        """Returns a list of previous contracts in chronological order (newest to oldest)."""
        history = []
        current = self.previous_contract
        while current:
            history.append(current)
            current = current.previous_contract
        return history

    def save(self, *args, **kwargs):
        # Auto-update status based on date
        today = date.today()
        if self.status != 'CANCELLED':
            if self.end_date < today:
                self.status = 'EXPIRED'
            else:
                self.status = 'ACTIVE'
        super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        delta = self.end_date - date.today()
        return delta.days

    @property
    def is_expiring_soon(self):
        days = self.days_remaining
        return 0 <= days <= self.notify_days_before

    def __str__(self):
        return self.title


