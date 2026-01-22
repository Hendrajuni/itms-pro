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
        # Active Incidents (Red Zone)
        context['active_incidents'] = DowntimeEvent.objects.filter(is_resolved=False).order_by('-start_time')
        # History (Green Zone)
        context['history_list'] = DowntimeEvent.objects.filter(is_resolved=True).order_by('-end_time')[:10]
        return context

class ReportDowntimeView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = DowntimeEvent
    fields = ['title', 'impact', 'node', 'asset', 'root_cause', 'description', 'start_time']
    template_name = 'network/downtime_form.html'
    success_url = reverse_lazy('downtime_list')
    
    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser

    def form_valid(self, form):
        form.instance.technician = self.request.user
        messages.error(self.request, "🚨 Downtime Reported! Notification sent to all users.")
        return super().form_valid(form)

class ResolveDowntimeView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = DowntimeEvent
    fields = ['resolution', 'end_time']
    template_name = 'network/downtime_resolve.html'
    success_url = reverse_lazy('downtime_list')
    
    def test_func(self):
        return self.request.user.groups.filter(name__in=['IT Support', 'Admin']).exists() or self.request.user.is_superuser
    
    def get_initial(self):
        return {'end_time': timezone.now()}
    
    def form_valid(self, form):
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
class NetworkNodeListView(LoginRequiredMixin, ListView):
    model = NetworkNode
    template_name = 'network/node_list.html'
    context_object_name = 'nodes'

    def get_queryset(self):
        qs = NetworkNode.objects.select_related('location').all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
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
        context['online_count'] = NetworkNode.objects.filter(status='Online').count()
        context['offline_count'] = NetworkNode.objects.filter(status='Offline').count()
        context['total_count'] = NetworkNode.objects.count()
        return context

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
