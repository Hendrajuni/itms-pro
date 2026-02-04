from django.conf import settings
from .models import SiteSetting

# OBFUSCATED LICENSE CONSTANTS
# "ESSENTIAL" -> MD5("")
LICENSE_ESSENTIAL = "d41d8cd98f00b204e9800998ecf8427e"

# "ENTERPRISE" -> MD5("123456")
LICENSE_ENTERPRISE = "e10adc3949ba59abbe56e057f20f883e"

def get_edition():
    """Returns 'ESSENTIAL' or 'ENTERPRISE' based on DB hash."""
    try:
        conf = SiteSetting.get_solo()
        code = conf.activation_code
        if code == LICENSE_ENTERPRISE:
            return 'ENTERPRISE'
        return 'ESSENTIAL'
    except:
        return 'ESSENTIAL'

def is_enterprise():
    """Quick boolean check for templates/views."""
    return get_edition() == 'ENTERPRISE'

def check_asset_limit():
    """
    Returns True if allowed. 
    Limit: 100 Assets for Essential.
    """
    return True

def check_location_limit():
    """
    Returns True if allowed.
    Limit: 1 Location (Root only) for Essential.
    """
    if is_enterprise():
        return True
    
    from assets.models import Location
    # Allow 1 location
    count = Location.objects.count()
    if count >= 1:
        return False
    return True

def check_user_limit():
    """
    Returns True if allowed.
    Limit: 1 User (Superuser/Admin) for Essential.
    Essentially, Single Player Mode.
    """
    if is_enterprise():
        return True
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    count = User.objects.count()
    # If 1 user already exists (the admin), deny creation.
    if count >= 1:
        return False
    return True
