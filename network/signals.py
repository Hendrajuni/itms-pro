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
            'description': f"Auto-synced from Asset: {instance.asset.name} (Legacy)"
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
    # --- Part A: Notifications ---
    # We only want to notify RELEVANT users, not everyone.
    if created or (instance.is_resolved and instance.end_time):
        from django.contrib.auth import get_user_model
        from notifications.models import Notification
        from django.db.models import Q
        User = get_user_model()
        
        target_location = instance.location or (instance.node.location if instance.node else None)
        
        # Recipient Logic
        recipients = set()
        
        # 1. Local Notification Logic
        if target_location:
            if instance.notify_everyone:
                # BROADCAST: Notify everyone in the location (Staff + IT)
                local_users = User.objects.filter(location=target_location)
                for u in local_users:
                    recipients.add(u)
            else:
                # DEFAULT: Notify ONLY IT Support in this location
                local_techs = User.objects.filter(groups__name='IT Support', location=target_location)
                for tech in local_techs:
                    recipients.add(tech)
                
        # 2. Technician (if assigned)
        if instance.technician:
            recipients.add(instance.technician)
            
        # 3. Admins (Always know)
        admins = User.objects.filter(is_superuser=True) | User.objects.filter(groups__name='Admin')
        for admin in admins:
            recipients.add(admin)
            
        # Prepare Message
        if created:
             title = f"🚨 NETWORK ALERT: {instance.title}"
             msg = f"Critical infrastructure DOWN.\nLocation: {target_location.name if target_location else 'Unknown'}\nImpact: {instance.get_impact_display()}."
        else:
             duration_str = str(instance.duration).split('.')[0]
             title = f"✅ RECOVERY: {instance.title}"
             msg = f"Incident resolved.\nLocation: {target_location.name if target_location else 'Unknown'}\nDuration: {duration_str}."

        # Bulk Create
        notifs = []
        for user in recipients:
            notifs.append(Notification(
                recipient=user,
                title=title,
                message=msg,
                link="/network/downtimes/",
                notification_type='System'
            ))
        
        if notifs:
            Notification.objects.bulk_create(notifs)

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
