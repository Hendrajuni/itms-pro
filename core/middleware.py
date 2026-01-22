from django.shortcuts import render, redirect
from django.urls import reverse
from .models import SiteSetting

class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            settings = SiteSetting.get_solo()
            if settings.maintenance_mode:
                # 1. Allow Static and Media
                if request.path.startswith('/static/') or request.path.startswith('/media/'):
                    return self.get_response(request)

                # 2. Allow Admin Panel
                if request.path.startswith('/admin/'):
                    return self.get_response(request)

                # 3. Allow Login and Logout Pages
                try:
                    login_url = reverse('login')
                    logout_url = reverse('logout')
                    if request.path == login_url or request.path == logout_url:
                        return self.get_response(request)
                except:
                    # Fallback if URLs not named standardly
                    pass

                # 4. Check User Privileges
                # 4. Check User Privileges
                if request.user.is_authenticated:
                    # STRICTER CHECK: Only Superusers and specific groups
                    # Removing 'is_staff' check as unrelated users might have it 
                    is_admin_group = request.user.groups.filter(name__in=['IT Support', 'Admin', 'Manager']).exists()
                    
                    if request.user.is_superuser or is_admin_group:
                        # Allow admins to proceed
                        return self.get_response(request)
                
                # 5. Block Everything Else
                return render(request, 'core/maintenance.html', status=503)

        except Exception as e:
            # Fallback in case of DB error or other issues to prevent total lockout
            print(f"Maintenance Middleware Error: {e}")
            pass

        return self.get_response(request)
