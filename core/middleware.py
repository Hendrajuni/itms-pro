from django.shortcuts import render, redirect
from django.urls import reverse
from .models import SiteSetting
from .license import is_enterprise
from django.http import HttpResponseForbidden
from django.contrib import messages

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
                    is_admin_group = request.user.groups.filter(name__in=['IT Support', 'Admin', 'Manager', 'Auditor']).exists()
                    
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


class LoginRequiredMiddleware:
    """
    Global middleware that forces login for all pages except whitelisted URLs.
    This prevents unauthenticated users from seeing any UI (including 404 pages with sidebar).
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Whitelist paths that don't require authentication
        self.exempt_urls = [
            '/accounts/login/',
            '/accounts/logout/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]

    def __call__(self, request):
        # Skip if user is already authenticated
        if request.user.is_authenticated:
            return self.get_response(request)
        
        # Check if path is exempt
        path = request.path
        for exempt in self.exempt_urls:
            if path.startswith(exempt) or path == exempt:
                return self.get_response(request)
                
        # Check dynamic exempt paths (like public asset reports)
        if path.startswith('/assets/print/'):
            return self.get_response(request)
        
        # Not authenticated and not exempt -> redirect to login
        from django.shortcuts import redirect
        from django.urls import reverse
        login_url = reverse('login')
        # Preserve the "next" parameter so user is redirected after login
        return redirect(f'{login_url}?next={path}')


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
            not 'favicon.ico' in request.path and
            not 'ajax' in request.path and
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
                
                # Friendly Name Logic - STRICTLY SIDEBAR MODULES ONLY
                # We group everything into these buckets.
                label = None
                icon = 'fas fa-circle'

                if url_name == 'index' or path == '/':
                    label = 'Dashboard'
                    icon = 'fas fa-home'
                
                # Inventory Group
                # --- NEW MAPPINGS (Prioritize over generic 'asset') ---
                elif 'analytics' in url_name:
                    label = 'Analytics'
                    icon = 'fas fa-chart-pie'
                elif 'disposal' in url_name:
                    label = 'Disposal Requests'
                    icon = 'fas fa-trash-alt'
                    
                elif 'asset' in url_name:
                    label = 'Assets' # Catch-all for Asset List, Detail, Create
                    icon = 'fas fa-laptop'
                elif 'software' in url_name or 'license' in url_name:
                    label = 'Software & Licenses'
                    icon = 'fas fa-compact-disc'
                elif 'contract' in url_name:
                    label = 'Contracts'
                    icon = 'fas fa-file-contract'
                
                # Infrastructure Group
                elif 'infra' in url_name:
                    label = 'Infrastructure'
                    icon = 'fas fa-server'
                elif 'network' in url_name or 'node' in url_name:
                    label = 'Network Nodes'
                    icon = 'fas fa-project-diagram'
                elif 'downtime' in url_name or 'monitor' in url_name:
                    label = 'NOC Monitor'
                    icon = 'fas fa-heartbeat'
                elif ('ip' in url_name and 'address' in url_name) or 'subnet' in url_name:
                    label = 'IP Address'
                    icon = 'fas fa-network-wired'

                # Operations Group
                elif 'ticket' in url_name:
                    label = 'Tickets'
                    icon = 'fas fa-ticket-alt'
                elif 'maintenance' in url_name:
                    label = 'Maintenance'
                    icon = 'fas fa-tools'
                elif 'article' in url_name or 'knowledge' in url_name:
                    label = 'Knowledge Base'
                    icon = 'fas fa-book'

                # Governance / Org (Optional, add if needed)
                elif 'project' in url_name:
                    label = 'Projects'
                    icon = 'fas fa-tasks'
                elif 'dailylog' in url_name:
                    label = 'Daily Logs'
                    icon = 'fas fa-clipboard-list'
                elif 'location' in url_name:
                    label = 'Locations'
                    icon = 'fas fa-map-marker-alt'
                elif 'user' in url_name or 'profile' in url_name:
                    label = 'Users' # or Profile
                    icon = 'fas fa-users'



                # If no label matched (e.g. unknown page), skip adding it to tabs 
                # OR fallback to generic if really needed. User said "Only Sidebar", so let's skip unknown.
                if label:
                    # Create Item
                    item = {'title': label, 'url': path, 'icon': icon}
                    
                    # LOGIC CHANGE: Group by TITLE (Label) instead of URL
                    # If this "Module" is already open, remove it so we can push it to the front (Active)
                    # This ensures we don't have "Infrastructure" AND "Infrastructure #7"
                    history = [h for h in history if h['title'] != label]
                    
                    # Append strictly new or updated version
                    history.append(item)
                    
                    # Limit to 6 tabs
                    if len(history) > 6:
                        history.pop(0)
                        
                    request.session['nav_history'] = history
            
            except Exception as e:
                # If resolve fails or other error, do nothing (don't break page)
                pass

        response = self.get_response(request)
        return response

class RestrictAdminMiddleware:
    """
    Restricts access to the Django Admin (/portal-admin/) to Enterprise/Pro Edition only.
    Use this to prevent Free users from accessing the admin panel directly via URL.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Change this if you renamed the admin URL in config/urls.py
        admin_path = '/portal-admin/'
        
        if request.path.startswith(admin_path):
            if not is_enterprise():
                # Option 1: Return 403 Forbidden
                # return HttpResponseForbidden("<h1>403 Forbidden</h1><p>Access to the Admin Portal is a Pro feature.</p>")
                
                # Option 2: Redirect to Dashboard with a Flash Message (Better UX)
                messages.error(request, "Access Denied: The Admin Portal is locked in the Free Edition.")
                return redirect('home')

        return self.get_response(request)

class ReadOnlyMiddleware:
    '''
    Restricts users in the 'Auditor' group to read-only access (GET, HEAD, OPTIONS).
    '''
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            '/accounts/login/',
            '/accounts/logout/',
        ]

    def __call__(self, request):
        if request.user.is_authenticated and request.user.groups.filter(name='Auditor').exists():
            if request.method not in ['GET', 'HEAD', 'OPTIONS']:
                is_exempt = any(request.path.startswith(url) for url in self.exempt_urls)
                if not is_exempt:
                    messages.error(request, 'Mode Read-Only: Anda tidak memiliki izin untuk menyimpan perubahan.')
                    from django.shortcuts import redirect
                    return redirect(request.META.get('HTTP_REFERER', '/'))
        return self.get_response(request)

