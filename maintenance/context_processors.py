from django.utils import timezone
from .models import AssetMaintenance, InfraMaintenance

def maintenance_status(request):
    """
    Provides global maintenance status like overdue counts to all templates.
    """
    if not request.user.is_authenticated:
        return {}

    # Only Admins/IT Support need to see this
    # if not (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'IT Support']).exists()):
    #     return {}
    
    # Simple count for badge
    today = timezone.now().date()
    
    # Optimize: Don't load full objects, just count
    overdue_assets = AssetMaintenance.objects.filter(
        scheduled_date__lt=today
    ).exclude(status__in=['Completed', 'Cancelled']).count()
    
    overdue_infra = InfraMaintenance.objects.filter(
        scheduled_date__lt=today
    ).exclude(status__in=['Completed', 'Cancelled']).count()
    
    total_overdue = overdue_assets + overdue_infra
    
    return {
        'global_overdue_count': total_overdue
    }
