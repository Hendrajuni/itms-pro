from django.db.models.signals import post_save
from django.dispatch import receiver
from tickets.models import Ticket
from network.models import NetworkNode
from .utils import send_telegram_message

@receiver(post_save, sender=Ticket)
def alert_new_ticket(sender, instance, created, **kwargs):
    # 1. Telegram Alert
    if created:
        message = (
            f"📩 *New Ticket Received*\n\n"
            f"*Title:* {instance.title}\n"
            f"*User:* {instance.created_by.username}\n"
            f"*Priority:* {instance.priority}"
        )
        send_telegram_message(message)
        
    # 2. In-App Notification
    recipient = instance.assigned_to
    
    from .models import Notification
    
    if recipient:
        action = "New Ticket Assigned" if created else "Ticket Updated"
        Notification.objects.create(
            recipient=recipient,
            title=f"{action}",
            message=f"Ticket #{instance.pk}: {instance.title}",
            link=f"/tickets/{instance.pk}/",
            notification_type='Ticket'
        )
    elif created:
        # If unassigned on creation, notify Managers/Admins
        from django.contrib.auth import get_user_model
        User = get_user_model()
        managers = User.objects.filter(groups__name__in=['Administrator', 'Manager']).distinct()
        
        for manager in managers:
            Notification.objects.create(
                recipient=manager,
                title="New Unassigned Ticket",
                message=f"New ticket from {instance.created_by.username}: {instance.title}",
                link=f"/tickets/{instance.pk}/",
                notification_type='Ticket'
            )

@receiver(post_save, sender=NetworkNode)
def alert_node_down(sender, instance, **kwargs):
    # Alert only if status is Offline
    if instance.status == 'Offline':
        message = (
            f"⚠️ *CRITICAL ALERT*\n\n"
            f"*Node:* {instance.name} is OFFLINE!\n"
            f"*IP:* {instance.ip_address}\n"
            f"*Location:* {instance.location}"
        )
        send_telegram_message(message)

# Import ProjectTask inside function (or top if possible, but avoid circular)
# Assuming ProjectTask is in governance.models
from governance.models import ProjectTask

@receiver(post_save, sender=ProjectTask)
def alert_project_task(sender, instance, created, **kwargs):
    if created and instance.assigned_to:
        from .models import Notification
        Notification.objects.create(
            recipient=instance.assigned_to,
            title="New Project Task",
            message=f"Project: {instance.project.name} - Task: {instance.name}",
            link=f"/governance/projects/{instance.project.pk}/",
            notification_type='Task'
        )
