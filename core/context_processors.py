from core.license import get_edition, is_enterprise
from core.models import SiteSetting

def site_branding(request):
    """
    Available in all templates as {{ site_settings }}
    """
    return {
        'site_settings': SiteSetting.get_solo()
    }

def license_processor(request):
    """
    Available in all templates as {{ is_enterprise }}, {{ is_demo_mode }}
    Usage in template: {% if is_enterprise %} ... {% endif %}
    """
    from django.conf import settings
    return {
        'edition_name': get_edition(),
        'is_enterprise': is_enterprise(),
        'is_demo_mode': getattr(settings, 'DEMO_MODE', False),
    }
