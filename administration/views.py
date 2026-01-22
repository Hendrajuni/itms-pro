from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View, UpdateView
from core.models import SiteSetting
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import SetPasswordForm
from django.contrib import messages
from django.db.models import Count, Q

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
        if loc_id:
            users = users.filter(location_id=loc_id)
            
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

class UserToggleStatusView(LoginRequiredMixin, SuperuserRequiredMixin, View):
    def post(self, request, pk):
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
from .forms import UserProfileForm

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
    fields = ['site_name', 'logo', 'favicon', 'login_background', 'maintenance_mode']
    template_name = 'administration/site_settings.html'
    success_url = reverse_lazy('site_settings')

    def get_object(self):
        return SiteSetting.get_solo()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Site Settings'
        return context
