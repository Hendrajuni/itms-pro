from django.db.models.signals import post_save
from django.dispatch import receiver
from assets.models import AssetIPAddress
from .models import IPAddress, Subnet
import ipaddress
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AssetIPAddress)
def sync_asset_ip_to_ipam(sender, instance, created, **kwargs):
    """
    Syncs IP Address from Assets module to Network IPAM.
    """
    ip_str = instance.ip_address
    if not ip_str:
        return

    try:
        current_ip = ipaddress.ip_address(ip_str)
    except ValueError:
        logger.warning(f"Invalid IP in AssetIPAddress: {ip_str}")
        return

    # 1. Find the matching Subnet
    found_subnet = None
    all_subnets = Subnet.objects.all()
    
    for subnet in all_subnets:
        try:
            net = ipaddress.ip_network(subnet.cidr, strict=False)
            if current_ip in net:
                found_subnet = subnet
                break
        except ValueError:
            continue

    if not found_subnet:
        logger.info(f"No matching subnet found for IP {ip_str}. Skipping IPAM sync.")
        return

    # 2. Register/Update in IPAddress
    # We use update_or_create to handle both new and existing IPs
    
    ip_obj, created = IPAddress.objects.update_or_create(
        subnet=found_subnet,
        address=str(current_ip),
        defaults={
            'asset': instance.asset,
            'node': None, # Ensure we don't conflict with Node if it's an Asset
            'status': 'Assigned',
            'description': f"Auto-synced from Asset: {instance.asset.name}"
        }
    )

from .models import DowntimeEvent
from .models import DowntimeEvent
from governance.models import DailyLog, DailyLogItem, RoutineTask
from django.utils import timezone

@receiver(post_save, sender=DowntimeEvent)
def log_incident_to_daily_job(sender, instance, created, **kwargs):
    """
    1. Logs resolved incidents to the technician's Daily Job.
    2. Sends System Notifications on Create/Resolve.
    """
    
    # --- Part A: Notifications ---
    if created:
        # New Incident: Notify Everyone
        from django.contrib.auth import get_user_model
        from notifications.models import Notification
        User = get_user_model()
        all_users = User.objects.filter(is_active=True)
        
        for user in all_users:
            Notification.objects.create(
                recipient=user,
                title=f"🚨 NETWORK ALERT: {instance.title}",
                message=f"Critical infrastructure DOWN. Impact: {instance.get_impact_display()}.",
                link="/network/downtimes/",
                notification_type='System'
            )
            
    elif instance.is_resolved and instance.end_time:
         # Resolved Incident: Notify Everyone
         from django.contrib.auth import get_user_model
         from notifications.models import Notification
         User = get_user_model()
         all_users = User.objects.filter(is_active=True)
         
         duration_str = str(instance.duration).split('.')[0] # Remove microseconds
         
         for user in all_users:
            Notification.objects.create(
                recipient=user,
                title=f"✅ RECOVERY: {instance.title}",
                message=f"Incident resolved. Duration: {duration_str}.",
                link="/network/downtimes/",
                notification_type='System'
            )

    # --- Part B: Daily Log (Only if resolved and has tech) ---
    if not instance.end_time or not instance.technician:
        return

    # 1. Get/Create DailyLog
    log, _ = DailyLog.objects.get_or_create(
        executor=instance.technician,
        date=timezone.localdate(),
        defaults={'status': 'Draft'}
    )

    # 2. Get/Create Routine Task Category
    task_cat, _ = RoutineTask.objects.get_or_create(
        name="Incident / Troubleshooting",
        defaults={
            'frequency': 'Daily',
            'category': 'Network'
        }
    )

    # 3. Create Log Item
    DailyLogItem.objects.create(
        log=log,
        task=task_cat,
        status='OK',
        note=f"[INCIDENT] {instance.title}. Duration: {instance.duration}. Fix: {instance.resolution}"
    )
