from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View, UpdateView, CreateView, DeleteView
from core.models import SiteSetting
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import SetPasswordForm
from django.contrib import messages
from django.db.models import Count, Q
from django.core.management import call_command
from django.core.management import call_command
from .forms import UserCreateForm, UserUpdateForm
from django.utils import timezone
import io
import json

User = get_user_model()

class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.groups.filter(name='Manager').exists()

class UserListView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    template_name = 'administration/user_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter Data
        from assets.models import Department, Location
        context['departments'] = Department.objects.all()
        context['locations'] = Location.objects.all()

        # Users with Group Annotations
        users = User.objects.select_related('department', 'location').prefetch_related('groups').order_by('username')
        
        # Filtering
        dept_id = self.request.GET.get('dept')
        loc_id = self.request.GET.get('loc')
        
        if dept_id:
            users = users.filter(department_id=dept_id)
            try:
                context['selected_dept'] = Department.objects.get(id=dept_id)
            except Department.DoesNotExist: pass
            
        if loc_id:
            try:
                selected_loc = Location.objects.get(id=loc_id)
                descendants = selected_loc.get_descendants(include_self=True)
                users = users.filter(location__in=descendants)
                context['selected_loc'] = selected_loc
            except Location.DoesNotExist: 
                pass
            
        # Context for Dropdowns
        context['location_roots'] = Location.objects.filter(parent__isnull=True).prefetch_related('children')

            
        # Execute Query (convert to list for caching/filtering in Python)
        
        # Add 'is_online' attribute based on cache
        from django.core.cache import cache
        user_list = []
        status_filter = self.request.GET.get('status')
        
        for user in users:
            last_seen = cache.get(f'user_last_seen_{user.id}')
            user.is_online = True if last_seen else False
            
            # Application Level Filtering for Online/Offline
            if status_filter == 'online' and not user.is_online:
                continue
            if status_filter == 'offline' and user.is_online:
                continue
                
            user_list.append(user)
            
        context['users'] = user_list
        
        # Groups with Member Count
        context['groups'] = Group.objects.annotate(user_count=Count('user')).all()
        
        # Stats
        context['total_users'] = User.objects.count()
        context['active_users'] = User.objects.filter(is_active=True).count()
        context['inactive_users'] = User.objects.filter(is_active=False).count()
        
        # Password Reset Form (Empty initially, handled via Modal/Post)
        context['password_form'] = SetPasswordForm(user=self.request.user) 
        
        return context

class UserCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    template_name = 'administration/user_form.html'
    form_class = UserCreateForm
    success_url = reverse_lazy('user_list')
    
    def form_valid(self, form):
        from core.license import check_user_limit
        if not check_user_limit():
             messages.error(self.request, "License Restriction: Essential Edition supports only 1 User (Admin). Upgrade to Enterprise.")
             return self.render_to_response(self.get_context_data(form=form))
             
        messages.success(self.request, f"User {form.instance.username} created successfully.")
        return super().form_valid(form)

class UserUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'administration/user_form.html'
    success_url = reverse_lazy('user_list')
    context_object_name = 'user_obj' # Avoid conflict with user context processor

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Edit User"
        return context

    def form_valid(self, form):
        messages.success(self.request, f"User {form.instance.username} updated successfully.")
        return super().form_valid(form)

class UserDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    model = User
    template_name = 'assets/confirm_delete.html'
    success_url = reverse_lazy('user_list')

    def dispatch(self, request, *args, **kwargs):
        # DEMO MODE: Block user deletion
        from django.conf import settings
        if getattr(settings, 'DEMO_MODE', False):
            messages.error(request, "This action is disabled in Demo Mode.")
            return redirect('user_list')
        # Prevent deleting yourself
        if str(kwargs.get('pk')) == str(request.user.pk):
             messages.error(request, "You cannot delete your own account.")
             return redirect('user_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete User"
        context['warning'] = f"Are you sure you want to delete user '{self.object.username}'? This action cannot be undone."
        return context

class UserToggleStatusView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def post(self, request, pk):
        # DEMO MODE: Block user toggle
        from django.conf import settings
        if getattr(settings, 'DEMO_MODE', False):
            messages.error(request, "This action is disabled in Demo Mode.")
            return redirect('user_list')
            
        user = get_object_or_404(User, pk=pk)
        
        # Prevent disabling oneself
        if user == request.user:
            messages.error(request, "You cannot disable your own account.")
            return redirect('user_list')
        
        user.is_active = not user.is_active
        user.save()
        
        status = "Activated" if user.is_active else "Deactivated"
        messages.success(request, f"User {user.username} has been {status}.")
        return redirect('user_list')

class AdminPasswordResetView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def post(self, request, pk):
        # DEMO MODE: Block password reset
        from django.conf import settings
        if getattr(settings, 'DEMO_MODE', False):
            messages.error(request, "Password reset is disabled in Demo Mode.")
            return redirect('user_list')
            
        user = get_object_or_404(User, pk=pk)
        form = SetPasswordForm(user, request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, f"Password for {user.username} has been reset successfully.")
        else:
            messages.error(request, "Error resetting password. Please try again.")
            
        return redirect('user_list')

from django.views.generic import UpdateView
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from .forms import UserProfileForm, DepartmentForm, RegionalHeadForm, UserCreateForm
from django.views.generic import CreateView, DeleteView, ListView
from assets.models import Department, DepartmentHead

class DepartmentListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    model = Department
    template_name = 'administration/department_list.html'
    context_object_name = 'departments'
    ordering = ['name']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = DepartmentForm() # For Create Modal
        
        # Regional Heads for Tab 2
        context['regional_heads'] = DepartmentHead.objects.select_related('department', 'location', 'manager').order_by('location__name', 'department__name')
        context['regional_form'] = RegionalHeadForm()
        return context

class DepartmentCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    success_url = reverse_lazy('department_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Department created successfully.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error creating department.")
        return redirect('department_list')

class DepartmentUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'administration/department_form.html'
    success_url = reverse_lazy('department_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Department updated successfully.")
        return super().form_valid(form)

class DepartmentDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    model = Department
    success_url = reverse_lazy('department_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Department deleted successfully.")
        return super().delete(request, *args, **kwargs)

# Regional Head Views
class RegionalHeadCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    model = DepartmentHead
    form_class = RegionalHeadForm
    success_url = reverse_lazy('department_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Regional Head assigned successfully.")
        return super().form_valid(form)
        
    def form_invalid(self, form):
        messages.error(self.request, "Error assigning regional head. Check duplicates.")
        return redirect('department_list')

class RegionalHeadDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    model = DepartmentHead
    success_url = reverse_lazy('department_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Regional Head assignment removed.")
        return super().delete(request, *args, **kwargs)

class UserProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'administration/user_profile.html'
    success_url = reverse_lazy('user_profile')
    
    def get_object(self):
        return self.request.user
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = 'info'
        return context
        
    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)

class UserChangePasswordView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'administration/user_profile.html'
    success_url = reverse_lazy('user_profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = 'security'
        return context
        
    def form_valid(self, form):
        messages.success(self.request, "Password updated successfully. Please login again if required.")
        return super().form_valid(form)

from itertools import chain
from operator import attrgetter
from assets.models import Asset
from network.models import NetworkNode, IPAddress
from tickets.models import Ticket

import csv
from django.http import HttpResponse    
from assets.models import Location # Ensure Location is imported

class UserExportView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Base Query
        users = User.objects.select_related('department', 'location').prefetch_related('groups').order_by('username')
        
        # Filter Logic (Same as ListView)
        dept_id = request.GET.get('dept')
        loc_id = request.GET.get('loc')
        status_filter = request.GET.get('status')
        
        if dept_id:
            users = users.filter(department_id=dept_id)
            
        if loc_id:
            try:
                selected_loc = Location.objects.get(id=loc_id)
                descendants = selected_loc.get_descendants(include_self=True)
                users = users.filter(location__in=descendants)
            except Location.DoesNotExist: pass
            
        # Prepare CSV Response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        
        writer = csv.writer(response)
        # Header
        writer.writerow(['Username', 'Full Name', 'Email', 'Role', 'Department', 'Location', 'Status', 'Last Login', 'Groups'])
        
        from django.core.cache import cache
        
        for user in users:
            # Check Status Filter
            last_seen = cache.get(f'user_last_seen_{user.id}')
            is_online = True if last_seen else False
            
            if status_filter == 'online' and not is_online:
                continue
            if status_filter == 'offline' and is_online:
                continue
                
            # Role
            role = "User"
            if user.is_superuser: role = "Superuser"
            elif user.is_staff: role = "Staff"
            
            # Groups
            groups = ", ".join([g.name for g in user.groups.all()])
            
            writer.writerow([
                user.username,
                user.get_full_name(),
                user.email,
                role,
                user.department.name if user.department else "-",
                user.location.name if user.location else "-",
                "Online" if is_online else "Offline",
                user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else "Never",
                groups
            ])
            
        return response

class UserPrintView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    template_name = 'administration/user_print.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        from assets.models import Department
        from django.core.cache import cache
        
        # Base Query
        users = User.objects.select_related('department', 'location').prefetch_related('groups').order_by('username')
        
        # Filter Logic
        dept_id = self.request.GET.get('dept')
        loc_id = self.request.GET.get('loc')
        status_filter = self.request.GET.get('status')
        
        # Filter Context Display
        filter_display = []
        
        if dept_id:
            users = users.filter(department_id=dept_id)
            try:
                d = Department.objects.get(id=dept_id)
                filter_display.append(f"Department: {d.name}")
            except: pass
            
        if loc_id:
            try:
                selected_loc = Location.objects.get(id=loc_id)
                descendants = selected_loc.get_descendants(include_self=True)
                users = users.filter(location__in=descendants)
                filter_display.append(f"Location: {selected_loc.name}")
            except Location.DoesNotExist: pass
            
        # Convert to list to handle properties
        user_list = []
        for user in users:
            last_seen = cache.get(f'user_last_seen_{user.id}')
            user.is_online = True if last_seen else False
            
            if status_filter == 'online' and not user.is_online:
                continue
            if status_filter == 'offline' and user.is_online:
                continue
            
            user_list.append(user)

        if status_filter:
            filter_display.append(f"Status: {status_filter.title()}")

        context['users'] = user_list
        context['filter_display'] = " | ".join(filter_display) if filter_display else "All Data"
        context['print_date'] = timezone.now()
        return context

class OrgChartView(LoginRequiredMixin, TemplateView):
    template_name = 'administration/org_chart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assets.models import Department, Location
        from django.db.models import Prefetch
        
        user = self.request.user

        # 1. Location Roots for Dropdown
        location_roots = Location.objects.filter(parent__isnull=True).prefetch_related('children')
        
        # IT Support Scope: Restrict Dropdown
        if not (user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()):
            if user.groups.filter(name='IT Support').exists() and hasattr(user, 'location') and user.location:
                root = user.location.root_node
                location_roots = location_roots.filter(id=root.id)

        context['location_roots'] = location_roots
        
        # 2. Determine Filter Location
        loc_id = self.request.GET.get('loc')
        
        # Auto-enforce scope for IT Support if no filter selected (Default to their region)
        if not loc_id and not (user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()):
             if hasattr(user, 'location') and user.location:
                  # Default to their root region
                  loc_id = user.location.root_node.id
        
        # 3. Prepare Employee Queryset based on Location
        # Start with all users
        employee_qs = User.objects.all().order_by('username')
        
        if loc_id:
            try:
                selected_loc = Location.objects.get(id=loc_id)
                context['selected_loc'] = selected_loc
                
                # Recursive location filter
                descendants = selected_loc.get_descendants(include_self=True)
                employee_qs = employee_qs.filter(location__in=descendants)
            except Location.DoesNotExist:
                pass
        
        # 4. Fetch Departments with Filtered Employees
        # We filter the 'employees' relation using Prefetch
        departments = Department.objects.select_related('manager').prefetch_related(
            Prefetch('employees', queryset=employee_qs)
        ).order_by('name')

        # 5. Map Regional Heads if location selected
        if loc_id:
             try:
                 from assets.models import DepartmentHead
                 # Fetch heads for this specific location
                 regional_heads = DepartmentHead.objects.filter(location_id=loc_id).select_related('manager')
                 reg_map = {rh.department_id: rh.manager for rh in regional_heads}
                 
                 for dept in departments:
                     if dept.id in reg_map:
                         dept.regional_manager = reg_map[dept.id]
             except Exception: pass

        context['departments'] = departments
        
        return context

class AuditLogListView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    template_name = 'administration/audit_log.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fetch Top 50 Changes from each Key Model
        # Note: 'history' manager is added by simple-history
        
        assets = Asset.history.select_related('history_user').order_by('-history_date')[:50]
        nodes = NetworkNode.history.select_related('history_user').order_by('-history_date')[:50]
        ips = IPAddress.history.select_related('history_user').order_by('-history_date')[:50]
        tickets = Ticket.history.select_related('history_user').order_by('-history_date')[:50]
        users = User.history.select_related('history_user').order_by('-history_date')[:50]
        
        # Combine
        combined_logs = sorted(
            chain(assets, nodes, ips, tickets, users), 
            key=attrgetter('history_date'), 
            reverse=True
        )
        
        # Process for Template (Avoid _meta access in template)
        display_logs = []
        for log in combined_logs[:100]:
            # Clean up Model Name (remove 'historical')
            # historical records usually include 'historical ' in verbose_name
            model_name = log._meta.verbose_name.replace('historical ', '').title()
            
            # Get String Representation (Handle deleted objects gracefully)
            try:
                # simple_history often proxies __str__, but let's be safe
                target_name = str(log.history_object) if log.history_object else "Deleted Record"
            except:
                target_name = f"Object #{log.history_id}"

            display_logs.append({
                'history_date': log.history_date,
                'history_user': log.history_user,
                'history_type': log.history_type,
                'history_id': log.history_id,
                'target': target_name,
                'model_name': model_name,
            })
        
        context['audit_logs'] = display_logs
        
        return context

class SiteSettingsView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    model = SiteSetting
    fields = ['site_name', 'company_name', 'company_address', 'company_phone', 'company_email', 'asset_id_prefix', 'logo', 'favicon', 'login_background', 'maintenance_mode']
    template_name = 'administration/site_settings.html'
    success_url = reverse_lazy('site_settings')

    def get_object(self):
        return SiteSetting.get_solo()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Site Settings'
        return context

class DatabaseBackupView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # buffer to capture stdout
        buffer = io.StringIO()
        
        # Dump all data (exclude sessions/contenttypes/auth permissions to keep it cleaner if desired, 
        # but full dump is safer for full restore. We exclude sessions/contenttypes to avoid issues)
        call_command('dumpdata', exclude=['contenttypes', 'sessions', 'admin'], indent=2, stdout=buffer)
        
        # Seek start
        buffer.seek(0)
        data = buffer.read()
        buffer.close()
        
        # Prepare Response
        timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M')
        filename = f"itms_backup_{timestamp}.json"
        
        response = HttpResponse(data, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

class DatabaseRestoreView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        # DEMO MODE: Block database restore
        from django.conf import settings as django_settings
        if getattr(django_settings, 'DEMO_MODE', False):
            messages.error(request, "Database restore is disabled in Demo Mode.")
            return redirect('site_settings')
            
        # 1. Check File
        if 'backup_file' not in request.FILES:
            messages.error(request, "Please upload a valid JSON backup file.")
            return redirect('site_settings')
            
        backup_file = request.FILES['backup_file']
        
        # 2. Save Temporary
        import os
        from django.conf import settings
        
        # Safety check extension
        if not backup_file.name.endswith('.json'):
             messages.error(request, "Invalid file format. Please upload a .json file.")
             return redirect('site_settings')
             
        # Save to temp directory
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_backups')
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"restore_{int(timezone.now().timestamp())}.json")
        
        try:
            with open(file_path, 'wb+') as destination:
                for chunk in backup_file.chunks():
                    destination.write(chunk)
                    
            # 3. Call Loaddata
            # Note: loaddata treats the input as fixture paths.
            call_command('loaddata', file_path)
            
            messages.success(request, "Database restored successfully! (Records updated/created)")
            
        except Exception as e:
            messages.error(request, f"Restore Failed: {str(e)}")
            
        finally:
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                
        return redirect('site_settings')
