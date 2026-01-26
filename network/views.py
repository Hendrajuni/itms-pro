from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from .models import DowntimeEvent, IPAddress, NetworkNode, ISPLine, Subnet

# --- Downtime Views ---
class DowntimeDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'network/downtime_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Filters
        branch_id = self.request.GET.get('branch')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Base Querysets
        active_qs = DowntimeEvent.objects.filter(is_resolved=False).select_related('node', 'node__location', 'technician')
        history_qs = DowntimeEvent.objects.filter(is_resolved=True).select_related('node', 'node__location', 'technician')

        # --- SCOPING LOGIC ---
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
        if not is_global:
            # Filter by User Location (and descendants)
            # Use Q objects for OR logic
            from django.db.models import Q
            
            if hasattr(user, 'location') and user.location:
                allowed_locations = user.location.get_descendants(include_self=True)
                # Visible if: Incident Location is in user's scope OR Node is in user's scope OR User is the assigned technician
                scope_filter = Q(location__in=allowed_locations) | Q(node__location__in=allowed_locations) | Q(technician=user)
                
                active_qs = active_qs.filter(scope_filter)
                history_qs = history_qs.filter(scope_filter)
            else:
                # If no location, currently showing nothing unless assigned
                active_qs = active_qs.filter(technician=user)
                history_qs = history_qs.filter(technician=user)

        # Apply Filters
        if branch_id:
            # Filter by the EXPLICIT location field, or fallback to node location if needed
            # But UI logic says "Branch/Location".
            active_qs = active_qs.filter(Q(location_id=branch_id) | Q(node__location_id=branch_id))
            history_qs = history_qs.filter(Q(location_id=branch_id) | Q(node__location_id=branch_id))
            
        if start_date:
            active_qs = active_qs.filter(start_time__date__gte=start_date)
            history_qs = history_qs.filter(start_time__date__gte=start_date)
            
        if end_date:
            active_qs = active_qs.filter(start_time__date__lte=end_date)
            history_qs = history_qs.filter(end_time__date__lte=end_date) # Use end_time for history resolution
            
        # Final ordering
        context['active_incidents'] = active_qs.order_by('-start_time')
        context['history_list'] = history_qs.order_by('-end_time')[:50] # Limit history to 50
        
        # Context for Filter Dropdowns
        if is_global:
            context['branches'] = Location.objects.order_by('name')
        else:
             if hasattr(user, 'location') and user.location:
                 descendants = user.location.get_descendants(include_self=True)
                 descendant_ids = [loc.id for loc in descendants]
                 context['branches'] = Location.objects.filter(id__in=descendant_ids).order_by('name')
             else:
                 context['branches'] = []
        
        return context

class ReportDowntimeView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = DowntimeEvent
    fields = ['title', 'impact', 'location', 'node', 'asset', 'root_cause', 'description', 'start_time']
    template_name = 'network/downtime_form.html'
    success_url = reverse_lazy('downtime_list')
    
    def get_initial(self):
        initial = super().get_initial()
        if hasattr(self.request.user, 'location') and self.request.user.location:
             initial['location'] = self.request.user.location
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        
        # Check if user is Global Admin/Manager
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
        if not is_global:
            if hasattr(user, 'location') and user.location:
                # Restrict Location Dropdown to User's Jurisdiction
                descendants = user.location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                
                # Filter Location
                form.fields['location'].queryset = Location.objects.filter(id__in=descendant_ids).order_by('name')
                
                # Filter Node (Device)
                from network.models import NetworkNode
                form.fields['node'].queryset = NetworkNode.objects.filter(location_id__in=descendant_ids).order_by('name')
                
                # Filter Asset
                from assets.models import Asset
                form.fields['asset'].queryset = Asset.objects.filter(location_id__in=descendant_ids).order_by('name')
                
            else:
                # If IT Support has no location, they shouldn't be here (or see nothing)
                form.fields['location'].queryset = Location.objects.none()
                form.fields['node'].queryset = NetworkNode.objects.none()
                form.fields['asset'].queryset = Asset.objects.none()
                
        return form

    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser

    def form_valid(self, form):
        from notifications.models import Notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Auto-assign technician to reporter so they can see it (visibility scope)
        form.instance.technician = self.request.user
        
        response = super().form_valid(form)
        downtime = self.object
        node = downtime.node
        
        # Ensure location is set on instance if node provided but loc missing
        # (Though field is in form now, so user sets it)
        if not downtime.location and node and node.location:
            downtime.location = node.location
            downtime.save(update_fields=['location'])
            
        incident_location = downtime.location
            
        # 3. Create Support Ticket (Work Queue)
        from tickets.models import Ticket
        
        ticket_priority = 'High'
        if downtime.impact == 'CRITICAL':
            ticket_priority = 'Critical'
            
        # Try to find asset from Node if not explicit
        target_asset = downtime.asset
        if not target_asset and node and node.asset:
            target_asset = node.asset
            
        ticket = Ticket.objects.create(
            title=f"Downtime: {downtime.title}",
            description=f"Auto-generated from NOC Incident Report.\n\nRoot Cause: {downtime.get_root_cause_display()}\n\n{downtime.description}",
            created_by=self.request.user,
            assigned_to=self.request.user, # Assign to reporter initially? Or leave open? User usually assigns to self if they report it.
            asset=target_asset,
            priority=ticket_priority,
            category='Network',
            status='Open'
        )

        messages.success(self.request, f"🚨 Downtime Reported! Ticket #{ticket.ticket_code} created.")
        return response

class ResolveDowntimeView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = DowntimeEvent
    fields = ['resolution', 'end_time', 'location']
    template_name = 'network/downtime_resolve.html'
    success_url = reverse_lazy('downtime_list')
    
    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser
    
    def get_initial(self):
        return {'end_time': timezone.now()}
    
    def form_valid(self, form):
        # Determine who is resolving
        if not form.instance.technician:
             form.instance.technician = self.request.user
             
        # Durations and is_resolved are handled by model.save()
        messages.success(self.request, "✅ Incident Resolved! Recovery notification sent.")
        return super().form_valid(form)

# --- Existing Stubs (Keep them minimal for now) ---
# --- IP Address Management (IPAM) ---
class IPAddressListView(LoginRequiredMixin, TemplateView):
    template_name = 'network/ipam_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subnets = Subnet.objects.prefetch_related('ips__node', 'ips__asset').all()
        
        # Sort IPs naturally? (192.168.1.2 before 192.168.1.10)
        # For simplicity, we trust standard ordering or add a custom sort later.
        
        context['subnets'] = subnets
        context['total_ips'] = IPAddress.objects.count()
        context['free_ips'] = IPAddress.objects.filter(status='Free').count()
        context['active_ips'] = IPAddress.objects.filter(status='Active').count()
        return context

class AssignIpView(LoginRequiredMixin, UpdateView):
    model = IPAddress
    fields = ['status', 'node', 'asset', 'mac_address', 'description']
    template_name = 'network/ipam_form.html'
    success_url = reverse_lazy('ip_list')

    def form_valid(self, form):
        messages.success(self.request, f"IP Address {form.instance.address} updated.")
        return super().form_valid(form)

# --- Device Manager (Nodes) ---
# --- Device Manager (Nodes) ---
class NetworkNodeListView(LoginRequiredMixin, ListView):
    model = NetworkNode
    template_name = 'network/node_list.html'
    context_object_name = 'nodes'

    def get_queryset(self):
        qs = NetworkNode.objects.select_related('location', 'infrastructure', 'asset').all()
        
        # --- SCOPING LOGIC ---
        user = self.request.user
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
        if not is_global:
            if hasattr(user, 'location') and user.location:
                # Use ID list to avoid efficiency issues
                descendants = user.location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                qs = qs.filter(location_id__in=descendant_ids)
            else:
                qs = qs.none()

        # --- FILTERS ---
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
            
        location_id = self.request.GET.get('location')
        if location_id:
            qs = qs.filter(location_id=location_id)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # View Mode Logic
        view_mode = self.request.GET.get('view')
        if view_mode in ['grid', 'list']:
            self.request.session['node_view_pref'] = view_mode
        else:
            view_mode = self.request.session.get('node_view_pref', 'grid')
            
        context['view_mode'] = view_mode
        
        # Use the Scoped QuerySet for counts!
        # Note: get_queryset() might have text filters if 'q' is present.
        # Ideally we want the scoped list WITHOUT the search filter for the general stats.
        
        # Re-calc scope without search term or filters for "Total Stats"
        qs_base = NetworkNode.objects.all()
        user = self.request.user
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
        if not is_global and hasattr(user, 'location') and user.location:
             descendants = user.location.get_descendants(include_self=True)
             descendant_ids = [loc.id for loc in descendants]
             qs_base = qs_base.filter(location_id__in=descendant_ids)
        elif not is_global:
             qs_base = qs_base.none()
             
        context['online_count'] = qs_base.filter(status='Online').count()
        context['offline_count'] = qs_base.filter(status='Offline').count()
        context['total_count'] = qs_base.count()
        
        # --- Filter Dropdown Context ---
        if is_global:
            context['locations'] = Location.objects.order_by('name')
        else:
             if hasattr(user, 'location') and user.location:
                 descendants = user.location.get_descendants(include_self=True)
                 descendant_ids = [loc.id for loc in descendants]
                 context['locations'] = Location.objects.filter(id__in=descendant_ids).order_by('name')
             else:
                 context['locations'] = []
        
        return context

from django import forms
from assets.models import Location, Infrastructure

class NetworkNodeForm(forms.ModelForm):
    class Meta:
        model = NetworkNode
        fields = ['name', 'type', 'location', 'infrastructure', 'ip_address', 'mac_address', 'asset', 'notes']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.order_by('name')
        self.fields['infrastructure'].queryset = Infrastructure.objects.order_by('name')
        # Optional: Filter Infrastructure by Location if location selected? (Dynamic JS needed, skipping for now)

class NetworkNodeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = NetworkNode
    form_class = NetworkNodeForm
    template_name = 'network/node_form.html'
    success_url = reverse_lazy('network_node_list')

    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, "Network Node added successfully.")
        return super().form_valid(form)

class NetworkNodeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = NetworkNode
    form_class = NetworkNodeForm
    template_name = 'network/node_form.html'
    success_url = reverse_lazy('network_node_list')

    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser
    
    def form_valid(self, form):
        messages.success(self.request, "Network Node updated successfully.")
        return super().form_valid(form)

class NetworkNodeDeleteView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    # Using TemplateView for a simple confirmation page or we can use DeleteView
    # But usually DeleteView requires a template.
    template_name = 'network/node_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['node'] = get_object_or_404(NetworkNode, pk=self.kwargs['pk'])
        return context
        
    def post(self, request, *args, **kwargs):
        node = get_object_or_404(NetworkNode, pk=self.kwargs['pk'])
        node.delete()
        messages.success(request, "Network Node deleted.")
        return redirect('network_node_list')

    def test_func(self):
        return self.request.user.groups.filter(name__in=['Admin']).exists() or self.request.user.is_superuser

# --- API: On-Demand Ping ---
from django.http import JsonResponse
from django.views import View
import subprocess
import platform

class PingNodeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        node = get_object_or_404(NetworkNode, pk=pk)
        
        if not node.ip_address:
            return JsonResponse({'status': 'error', 'message': 'No IP Address configured'}, status=400)

        # OS-specific ping command
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '-w', '2000', node.ip_address]  # 1 packet, 2s timeout
        
        try:
            # Run Ping
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            is_online = (result.returncode == 0)
            
            # Update Node Status
            node.status = 'Online' if is_online else 'Offline'
            node.last_checked = timezone.now()
            node.save(update_fields=['status', 'last_checked'])
            
            return JsonResponse({
                'status': 'success',
                'node_status': node.status,
                'last_checked': node.last_checked.strftime("%H:%M:%S")
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class SubnetPrintView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Subnet
    template_name = 'network/subnet_print.html'
    context_object_name = 'subnet'
    
    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ip_addresses'] = self.object.ips.select_related('asset', 'node').order_by('address')
        context['print_date'] = timezone.now()
        context['printed_by'] = self.request.user
        return context

class SubnetListView(LoginRequiredMixin, TemplateView):
    template_name = 'core/under_construction.html'

class ISPLineListView(LoginRequiredMixin, TemplateView):
    template_name = 'core/under_construction.html'
