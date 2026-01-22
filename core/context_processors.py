from .models import SiteSetting

def site_branding(request):
    """
    Context processor to make SiteSetting available in all templates.
    """
    return {
        'site_settings': SiteSetting.get_solo()
    }
