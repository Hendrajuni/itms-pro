from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProjectTask
from notifications.models import Notification

@receiver(post_save, sender=ProjectTask)
def notify_new_task(sender, instance, created, **kwargs):
    """
    Triggers when a ProjectTask is created or updated.
    Sends notification to the assigned user.
    """
    if instance.assigned_to:
        
        # Determine Title and Message
        if created:
            title = "New Task Assigned"
            message = f"You have been assigned a new task: '{instance.name}' in project '{instance.project.name}'."
        else:
            title = "Task Updated"
            message = f"Task '{instance.name}' (Project: {instance.project.name}) has been updated."
            
            # Avoid spamming on minor updates; maybe check if assigned_to changed?
            # For now, simple logic: if it's just created or if status changed to 'Completed' (optional logic elsewhere)
            # Let's keep it simple: notify on assign/create.
            if not created: 
               # Logic to prevent excessive notifications on simple saves could be added here
               # For now, we will notify on every save if assigned. 
               pass 

        # Create Notification if not self-assigned (optional, but good practice)
        # Assuming we can't easily check 'request.user' inside signal without middleware context
        
        Notification.objects.create(
            recipient=instance.assigned_to,
            title=title,
            message=message,
            notification_type='Task',
            link=f"/governance/projects/{instance.project.pk}/" # Link to project detail
        )
