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
        
        # Imports
        from django.db.models import Q
        
        # Base Querysets
        active_qs = DowntimeEvent.objects.filter(is_resolved=False).select_related('node', 'node__location', 'technician')
        history_qs = DowntimeEvent.objects.filter(is_resolved=True).select_related('node', 'node__location', 'technician')

        # --- SCOPING LOGIC ---
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
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
    fields = ['title', 'impact', 'location', 'node', 'asset', 'root_cause', 'description', 'start_time', 'notify_everyone']
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
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
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
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
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
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
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

class SubnetListView(LoginRequiredMixin, ListView):
    model = Subnet
    template_name = 'network/subnet_dashboard.html'
    context_object_name = 'subnets'

    def get_queryset(self):
        qs = Subnet.objects.select_related('location').prefetch_related('ips').all()
        
        # --- SCOPING LOGIC ---
        user = self.request.user
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
        if not is_global:
            if hasattr(user, 'location') and user.location:
                descendants = user.location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                # Filter Subnets owned by these locations
                # We also might want to include "Global" subnets if location is None? 
                # For now strict scoping: Only my branch's subnets.
                qs = qs.filter(location_id__in=descendant_ids)
            else:
                qs = qs.none()
                
        # Order by Location Name then Subnet Name (For Regrouping)
        return qs.order_by('location__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Quick Stats (Based on visible subnets)
        subnets = self.get_queryset()
        
        total_ips = 0
        free_ips = 0
        active_ips = 0
        reserved_ips = 0
        
        # This might be heavy if many subnets. 
        # Optimization: Aggregate if possible, but IPAddress is separate model.
        # Let's count via IPAddress filtered by these subnets.
        subnet_ids = subnets.values_list('id', flat=True)
        from network.models import IPAddress
        
        # Base IP Queryset
        ip_qs = IPAddress.objects.filter(subnet_id__in=subnet_ids)
        
        context['total_ips'] = ip_qs.count()
        context['free_ips'] = ip_qs.filter(status='Free').count()
        context['active_ips'] = ip_qs.filter(status='Active').count()
        context['reserved_ips'] = ip_qs.filter(status='Reserved').count()
        
        return context

from .forms import SubnetForm, IPAddressForm

class SubnetCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Subnet
    form_class = SubnetForm
    template_name = 'network/subnet_form.html'
    success_url = reverse_lazy('subnet_list')

    def test_func(self):
        # Admins or IT Support (depending on policy, maybe only Managers?)
        return self.request.user.groups.filter(name__in=['Administrator', 'Manager', 'IT Support']).exists() or self.request.user.is_superuser

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        location_id = self.request.GET.get('location')
        if location_id:
             initial['location'] = location_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'location' in self.request.GET:
             from assets.models import Location
             context['locked_location'] = Location.objects.filter(pk=self.request.GET['location']).first()
        return context

    def form_valid(self, form):
        # Auto-Generate Name: [Location] - VLAN [ID] ([CIDR])
        location = form.cleaned_data.get('location')
        vlan = form.cleaned_data.get('vlan_id')
        cidr = form.cleaned_data.get('cidr') 
        
        parts = []
        if location:
            parts.append(location.name)
        if vlan:
             parts.append(f"VLAN {vlan}")
             
        # Always include CIDR for uniqueness
        parts.append(f"({cidr})")
            
        generated_name = " - ".join(parts)
        form.instance.name = generated_name
        
        # Check uniqueness manually since we bypassed form clean
        if Subnet.objects.filter(name=generated_name).exists():
             form.add_error(None, f"A subnet with the auto-generated name '{generated_name}' already exists.")
             return self.form_invalid(form)
             
        messages.success(self.request, f"Subnet '{generated_name}' created successfully.")
        return super().form_valid(form)



class SubnetDetailView(LoginRequiredMixin, DetailView):
    model = Subnet
    template_name = 'network/subnet_detail.html'
    context_object_name = 'subnet'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Prefetch related IPs to avoid N+1
        ips = self.object.ips.select_related('node', 'asset').order_by('address')
        context['ips'] = ips
        context['total_count'] = ips.count()
        context['active_count'] = ips.filter(status='Active').count()
        context['free_count'] = ips.filter(status='Free').count()
        context['reserved_count'] = ips.filter(status='Reserved').count()
        context['usage_percent'] = self.object.usage_percent()
        return context

class ISPLineListView(LoginRequiredMixin, TemplateView):
    template_name = 'core/under_construction.html'

class IPAddressCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = IPAddress
    form_class = IPAddressForm
    template_name = 'network/ip_form.html'

    def get_success_url(self):
        return reverse_lazy('subnet_detail', kwargs={'pk': self.kwargs['subnet_id']})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.subnet = get_object_or_404(Subnet, pk=self.kwargs['subnet_id'])
        kwargs['subnet'] = self.subnet
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subnet'] = self.subnet
        return context

    def form_valid(self, form):
        form.instance.subnet = self.subnet
        messages.success(self.request, f"IP Address {form.instance.address} added successfully.")
        return super().form_valid(form)

    def test_func(self):
        return self.request.user.groups.filter(name__in=['Administrator', 'Manager', 'IT Support']).exists() or self.request.user.is_superuser

class IPAddressUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = IPAddress
    form_class = IPAddressForm
    template_name = 'network/ip_form.html'

    def get_success_url(self):
        return reverse_lazy('subnet_detail', kwargs={'pk': self.object.subnet.id})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['subnet'] = self.object.subnet
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subnet'] = self.object.subnet
        context['editing'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, f"IP Address {form.instance.address} updated successfully.")
        return super().form_valid(form)

    def test_func(self):
        return self.request.user.groups.filter(name__in=['Administrator', 'Manager', 'IT Support']).exists() or self.request.user.is_superuser

# --- New IPAM Tree View Dashboard ---
from assets.models import Location 

class SubnetTreeDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'network/subnet_tree_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Sidebar: Root Locations
        # Apply scope filtering similar to Org Chart
        location_roots = Location.objects.filter(parent__isnull=True).prefetch_related('children')
        
        if not (user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()):
             if user.groups.filter(name='IT Support').exists() and hasattr(user, 'location') and user.location:
                  root = user.location.get_root()
                  location_roots = location_roots.filter(id=root.id)
        
        context['location_roots'] = location_roots
        context['is_manager'] = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
        # Also auto-select location if passed in GET or user default
        loc_id = self.request.GET.get('loc')
        if not loc_id and not context['is_manager'] and hasattr(user, 'location') and user.location:
             loc_id = user.location.id # Or root node
             
        if loc_id:
             context['selected_location_id'] = loc_id
             
        return context

class SubnetListAjaxView(LoginRequiredMixin, TemplateView):
    template_name = 'network/partials/subnet_list_partial.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loc_id = self.kwargs.get('pk')
        
        # 1. Location Info
        location = get_object_or_404(Location, pk=loc_id)
        context['location'] = location
        
        # 2. Filter Subnets (Self + Descendants)
        # Note: Location.get_descendants returns a list (custom override), we need IDs
        descendants_list = location.get_descendants(include_self=True)
        descendant_ids = [d.id for d in descendants_list]
        
        subnets = Subnet.objects.filter(location_id__in=descendant_ids).order_by('location__name', 'name')
        
        # 3. Stats logic (reused from ListView but tailored)
        total_ips = 0
        free_ips = 0
        active_ips = 0
        reserved_ips = 0
        
        # Aggregate IP Counts efficiently
        subnet_ids = subnets.values_list('id', flat=True)
        ip_qs = IPAddress.objects.filter(subnet_id__in=subnet_ids)
        
        context['total_ips'] = ip_qs.count()
        context['free_ips'] = ip_qs.filter(status='Free').count()
        context['active_ips'] = ip_qs.filter(status='Active').count()
        context['reserved_ips'] = ip_qs.filter(status='Reserved').count()
        context['subnets'] = subnets
        
        return context
