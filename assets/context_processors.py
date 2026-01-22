from notifications.models import Notification

def notification_ctx(request):
    if request.user.is_authenticated:
        # Get unread count
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        
        # Get recent notifications (both read and unread, but prioritize unread)
        my_notifications = Notification.objects.filter(recipient=request.user).order_by('-is_read', '-created_at')[:10]
        
        return {
            'unread_count': unread_count,
            'my_notifications': my_notifications
        }
    return {}
