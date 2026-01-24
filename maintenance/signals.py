from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AssetMaintenance, InfraMaintenance
from notifications.models import Notification
from notifications.utils import send_telegram_message

@receiver(post_save, sender=AssetMaintenance)
def notify_asset_maintenance_assignment(sender, instance, created, **kwargs):
    if instance.technician:
        # Check if created or if technician changed?
        # For simplicity, if created with technician or if saved/updated with technician
        # We can optimize to avoid spam on every edit, but for now let's notify.
        # Ideally check if 'technician' field is in update_fields or if it changed from DB.
        
        # Simple Logic: If not completed/cancelled, notify.
        if instance.status not in ['Completed', 'Cancelled']:
            title = f"New Asset Maintenance: {instance.title}"
            message = f"You have been assigned to maintain asset {instance.asset.name}. Scheduled: {instance.scheduled_date}"
            link = f"/maintenance/"  # Go to dashboard or specific detail if we had one separate
            
            # Avoid duplicate notification for same event? 
            # (Simplification: Just create it, user can read/delete)
            Notification.objects.create(
                recipient=instance.technician,
                title=title,
                message=message,
                link=link,
                notification_type='Maintenance'
            )
            
            # Send Telegram
            try:
                msg = f"🔧 *Maintenance Assignment*\n\nTitle: {instance.title}\nAsset: {instance.asset.name}\nTech: {instance.technician.username}\nDate: {instance.scheduled_date}"
                send_telegram_message(msg)
            except Exception as e:
                pass

@receiver(post_save, sender=InfraMaintenance)
def notify_infra_maintenance_assignment(sender, instance, created, **kwargs):
    if instance.technician:
        if instance.status not in ['Completed', 'Cancelled']:
            title = f"New Infra Maintenance: {instance.title}"
            message = f"You have been assigned to maintain infrastructure {instance.infrastructure.name}. Scheduled: {instance.scheduled_date}"
            link = f"/maintenance/"
            
            Notification.objects.create(
                recipient=instance.technician,
                title=title,
                message=message,
                link=link,
                notification_type='Maintenance'
            )
            
            try:
                msg = f"🏗 *Infra Maintenance Assignment*\n\nTitle: {instance.title}\nInfra: {instance.infrastructure.name}\nTech: {instance.technician.username}\nDate: {instance.scheduled_date}"
                send_telegram_message(msg)
            except Exception as e:
                pass
