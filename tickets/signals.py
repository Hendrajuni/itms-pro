from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.db.models import Q
from .models import Ticket
from notifications.models import Notification
from django.contrib.auth import get_user_model

@receiver(post_save, sender=Ticket)
def notify_it_staff_on_ticket_creation(sender, instance, created, **kwargs):
    """
    Broadcasts a notification to relevant IT Support staff when a new ticket is created.
    Target Audience: IT Staff whose location jurisdiction covers the ticket's location.
    """
    if created:
        User = get_user_model()
        
        # 1. Determine Ticket Location
        ticket_location = None
        if instance.asset and instance.asset.location:
            ticket_location = instance.asset.location
        elif instance.created_by and hasattr(instance.created_by, 'location'):
            ticket_location = instance.created_by.location
            
        # If we can't determine location, maybe notify all Admins/Managers? 
        # For now, let's stick to the plan. If no location, maybe only Global Admins see it.
        
        # 2. Find IT Support Group
        try:
            it_group = Group.objects.get(name='IT Support')
        except Group.DoesNotExist:
            return # No IT Support group defined

        # 3. Filter IT Staff based on Hierarchy
        # We want users where: user.location contains ticket_location in its descendants
        # OR user is Superuser/Admin (Global)
        
        # Get all IT Staff first (optimization: can be improved with complex query but loop is fine for small team)
        it_staff_candidates = User.objects.filter(groups=it_group).select_related('location')
        
        recipients = []
        
        for user in it_staff_candidates:
            should_notify = False
            
            # Scenario A: User is Global Admin / Superuser (Always Notify)
            if user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists():
                should_notify = True
            
            # Scenario B: User has Location & Ticket has Location
            elif user.location and ticket_location:
                # Check if ticket_location is within user's jurisdiction
                # Jurisdiction = User.location + Descendants
                # We can check: Is ticket_location IN user.location.get_descendants(include_self=True)?
                
                # Note: This might be slightly expensive if called often in loop, 
                # but get_descendants usually does a recursive DB call.
                # Optimization: Cache descendants IDs?
                # Let's trust the model method for now.
                
                jurisdiction = user.location.get_descendants(include_self=True)
                if ticket_location in jurisdiction:
                    should_notify = True
            
            # Scenario C: Ticket has NO location (e.g. created by user without profile location)
            elif not ticket_location:
                # Fallback: If unknown location, ONLY notify Global Admins/Managers.
                # Do NOT broadcast to all regional IT to avoid noise.
                should_notify = False
                
            if should_notify and user != instance.created_by: # Don't notify the creator
                recipients.append(user)

        # 4. Bulk Create Notifications
        notifications = []
        for recipient in recipients:
            notifications.append(Notification(
                recipient=recipient,
                title=f"New Ticket: {instance.ticket_code}",
                message=f"New ticket from {instance.created_by.get_full_name() or instance.created_by.username} at {ticket_location if ticket_location else 'Unknown Location'}.\nTopic: {instance.topic or instance.title}",
                link=f"/tickets/{instance.pk}/",
                notification_type='Ticket'
            ))
        
        if notifications:
            Notification.objects.bulk_create(notifications)
