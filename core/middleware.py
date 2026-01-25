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


class NavigationHistoryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request (Before View)
        # We do this logic BEFORE the view runs so the 'active' tab is present in the context immediately
        
        if (request.method == 'GET' and 
            not request.headers.get('x-requested-with') == 'XMLHttpRequest' and
            not request.path.startswith('/static/') and 
            not request.path.startswith('/media/') and
            not request.path.startswith('/admin/') and 
            not request.path.startswith('/api/') and
            not 'ajax' in request.path and
            not 'details' in request.path and
            not 'login' in request.path and
            not 'logout' in request.path):
            
            # Logic to add to session
            history = request.session.get('nav_history', [])
            
            # Generate Label
            path = request.path
            import re
            from django.urls import resolve
            
            try:
                match = resolve(path)
                url_name = match.url_name
                
                # Friendly Name Logic
                if url_name == 'index' or path == '/':
                    label = 'Dashboard'
                    icon = 'fas fa-home'
                elif 'asset' in url_name:
                    label = 'Assets'
                    icon = 'fas fa-laptop'
                    if 'create' in url_name: label = 'New Asset'
                    if 'detail' in url_name: label = 'Asset Details'
                elif 'software' in url_name:
                    label = 'Software'
                    icon = 'fas fa-compact-disc'
                elif 'contract' in url_name:
                    label = 'Contracts'
                    icon = 'fas fa-file-contract'
                elif 'infra' in url_name:
                    label = 'Infrastructure'
                    icon = 'fas fa-server'
                elif 'ticket' in url_name:
                    label = 'Tickets'
                    icon = 'fas fa-ticket-alt'
                else:
                    label = url_name.replace('_', ' ').title()
                    icon = 'fas fa-circle'
                
                # Specific overrides for detailed views if possible? 
                # Ideally we'd get the object string representation, but that requires View execution.
                # For now, generic labels or "Asset #123" (if we parse PK)
                if 'pk' in match.kwargs:
                    label += f" #{match.kwargs['pk']}"

            except:
                label = path.strip('/').split('/')[-1].title()
                icon = 'fas fa-link'
                if not label: 
                    label = "Home"
                    icon = 'fas fa-home'

            # Create Item
            item = {'title': label, 'url': path, 'icon': icon}
            
            # Remove existing instance of this URL to move it to the end (MRU)
            history = [h for h in history if h['url'] != path]
            
            # Append new
            history.append(item)
            
            # Limit to 6 tabs
            if len(history) > 6:
                history.pop(0)
                
            request.session['nav_history'] = history

        response = self.get_response(request)
        return response
