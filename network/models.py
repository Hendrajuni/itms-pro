from django.db import models
from django.conf import settings
from django.utils import timezone
from assets.models import Location, Vendor, Asset

class ISPLine(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    name = models.CharField(max_length=200, help_text="e.g., Biznet Dedicated")
    provider = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='isp_lines')
    cid_number = models.CharField(max_length=100, help_text="Customer ID / Circuit ID")
    capacity_mbps = models.IntegerField(help_text="Bandwidth in Mbps")
    ip_static_public = models.GenericIPAddressField(protocol='both', unpack_ipv4=False, null=True, blank=True)
    contract_start = models.DateField()
    contract_end = models.DateField()
    monthly_cost = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    support_phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.name} ({self.provider.name})"

from simple_history.models import HistoricalRecords

class NetworkNode(models.Model):
    TYPE_CHOICES = [
        ('Server', 'Server'),
        ('Router', 'Router'),
        ('Switch', 'Switch'),
        ('Firewall', 'Firewall'),
        ('Access_Point', 'Access Point'),
        ('CCTV', 'CCTV'),
        ('Printer', 'Printer'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('Online', 'Online'),
        ('Offline', 'Offline'),
        ('Maintenance', 'Maintenance'),
        ('Unknown', 'Unknown'),
    ]
    history = HistoricalRecords()
    name = models.CharField(max_length=200, help_text="e.g., Core Switch Lt 2")
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    infrastructure = models.ForeignKey('assets.Infrastructure', on_delete=models.SET_NULL, null=True, blank=True, related_name='network_nodes', help_text="Rack/Tower location")
    asset = models.OneToOneField(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name='network_node', help_text="Link to Asset Inventory if exists")
    
    ip_address = models.GenericIPAddressField(protocol='both', unpack_ipv4=False, null=True, blank=True, help_text="Management IP (Required for Ping)")
    mac_address = models.CharField(max_length=50, blank=True, help_text="e.g., 00:1A:2B:3C:4D:5E")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unknown', help_text="Updated via Ping Tool")
    last_checked = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

class Subnet(models.Model):
    name = models.CharField(max_length=200, help_text="e.g., Server Farm VLAN 10")
    cidr = models.CharField(max_length=50, help_text="e.g., 192.168.10.0/24")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='subnets', help_text="Branch/Site owner of this subnet")
    gateway = models.GenericIPAddressField(protocol='both', unpack_ipv4=False, null=True, blank=True)
    vlan_id = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    def usage_percent(self):
        try:
            import ipaddress
            network = ipaddress.ip_network(self.cidr, strict=False)
            total_ips = network.num_addresses - 2 # Subtract Network and Broadcast
            if total_ips <= 0:
                total_ips = 1 # Prevent division by zero
                
            used_ips = self.ips.exclude(status='Free').count()
            percent = int((used_ips / total_ips) * 100)
            return min(percent, 100) # Cap at 100
        except ValueError:
            return 0

    def __str__(self):
        return f"{self.name} ({self.cidr})"

class IPAddress(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Free', 'Free'),
        ('Reserved', 'Reserved'),
        ('DHCP', 'DHCP'),
    ]
    history = HistoricalRecords()
    subnet = models.ForeignKey(Subnet, on_delete=models.CASCADE, related_name='ips')
    address = models.GenericIPAddressField(protocol='both', unpack_ipv4=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Free')
    
    node = models.ForeignKey(NetworkNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='ip_allocations', help_text="Linked Network Device")
    asset = models.ForeignKey('assets.Asset', on_delete=models.SET_NULL, null=True, blank=True, related_name='ip_allocations', help_text="Linked General Asset (e.g. Laptop/PC)")
    
    mac_address = models.CharField(max_length=50, blank=True)
    anydesk_id = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, help_text="e.g., Reserved for New Printer")
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Automation Logic
        if self.node or self.asset:
            self.status = 'Active'
        elif self.status == 'Active' and not (self.node or self.asset):
            # If it WAS assigned but now Node/Asset is gone, free it up 
            self.status = 'Free'
        
        super().save(*args, **kwargs)

    def __str__(self):
        if self.node:
            return f"{self.address} ({self.node.name})"
        elif self.asset:
            return f"{self.address} ({self.asset.name})"
        return f"{self.address} ({self.status})"

class DowntimeEvent(models.Model):
    ROOT_CAUSE_CHOICES = [
        ('Power Failure', 'Power Failure'),
        ('Hardware Failure', 'Hardware Failure'),
        ('Software/Bug', 'Software/Bug'),
        ('ISP Issue', 'ISP Issue'),
        ('Human Error', 'Human Error'),
        ('Maintenance', 'Maintenance'),
        ('Other', 'Other'),
    ]

    IMPACT_CHOICES = [
        ('High', 'High (Site Down)'),
        ('Medium', 'Medium (Partial)'),
        ('Low', 'Low (Minor)'),
    ]

    title = models.CharField(max_length=200)
    node = models.ForeignKey(NetworkNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    asset = models.ForeignKey('assets.Asset', on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='downtime_events', help_text="Affected Location")
    infrastructure = models.ForeignKey('assets.Infrastructure', on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True, editable=False)
    
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    root_cause = models.CharField(max_length=50, choices=ROOT_CAUSE_CHOICES, default='Other')
    impact = models.CharField(max_length=20, choices=IMPACT_CHOICES, default='Medium')
    description = models.TextField(blank=True, help_text="Detailed description of the incident")
    resolution = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)

    def calculate_duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        return timezone.now() - self.start_time

    def save(self, *args, **kwargs):
        # 1. Calculate Duration
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time
            self.is_resolved = True
        else:
            self.duration = None
            self.is_resolved = False

        # 2. Automation: Update Node Status
        if self.node:
            if not self.is_resolved:
                # Active Incident -> Node Offline
                self.node.status = 'Offline'
                self.node.save(update_fields=['status'])
            else:
                # Resolved -> Node Online
                self.node.status = 'Online'
                self.node.save(update_fields=['status'])

        super().save(*args, **kwargs)

    def __str__(self):
        status = "[RESOLVED]" if self.is_resolved else "[ACTIVE]"
        return f"{status} {self.title}"
