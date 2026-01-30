from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Q
from itertools import chain
from .models import AssetMaintenance, InfraMaintenance, MaintenanceSchedule
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages

class MaintenanceDashboardView(LoginRequiredMixin, ListView):
    template_name = 'maintenance/maintenance_dashboard.html'
    context_object_name = 'all_tasks'
    paginate_by = 100 # Not really used in Kanban, but for list fallback

    def get_queryset(self):
        user = self.request.user
        
        # 1. Base Query
        asset_tasks = AssetMaintenance.objects.all().select_related('asset', 'technician').order_by('scheduled_date')
        infra_tasks = InfraMaintenance.objects.all().select_related('infrastructure', 'technician').order_by('scheduled_date')
        
        # 2. RBAC / Location Filtering
        # If not superuser and not 'Head IT' (assuming group name), restrict to site hierarchy
        is_manager = user.is_superuser or user.groups.filter(name='Head IT').exists()
        
        if not is_manager:
            # Get user's location and descendants
            user_loc = getattr(user, 'location', None)
            if user_loc:
                subtree = user_loc.get_descendants(include_self=True)
                subtree_ids = [loc.id for loc in subtree]
                
                asset_tasks = asset_tasks.filter(asset__location_id__in=subtree_ids)
                infra_tasks = infra_tasks.filter(infrastructure__location_id__in=subtree_ids)
            else:
                # If user has no location assigned, maybe show nothing or just their own assigned tasks?
                # Safer default: Show only where they are technician or assigned
                asset_tasks = asset_tasks.filter(technician=user)
                infra_tasks = infra_tasks.filter(technician=user)

        # 3. Filtering (Dashboard Dropdown)
        location_filter = self.request.GET.get('location')
        if location_filter:
             asset_tasks = asset_tasks.filter(asset__location_id=location_filter)
             infra_tasks = infra_tasks.filter(infrastructure__location_id=location_filter)

        # 4. Combine
        from itertools import chain
        combined = sorted(chain(asset_tasks, infra_tasks), key=lambda x: x.scheduled_date)
        return combined

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tasks = context['all_tasks'] # This is a list now because of chain/sorted
        
        today = timezone.now().date()
        
        # --- KANBAN BUCKETS ---
        scheduled = []
        progress = []
        hold = []     # Overdue or Waiting
        completed = []
        
        for task in all_tasks:
            # Decorate with helpers
            if hasattr(task, 'asset'):
                task.location_name = task.asset.location.name if task.asset.location else "-"
            else:
                task.location_name = task.infrastructure.location.name if task.infrastructure.location else "-"
                
            # Status Logic
            s = task.status
            if s == 'Completed':
                task.status_color = 'success'
                completed.append(task)
            elif task.scheduled_date < today:
                # CRITICAL: If strictly overdue, move to Overdue/Hold regardless of "In Progress" or "Scheduled"
                # This ensures the "Critical/Overdue" KPI matches the Kanban column count.
                task.status_color = 'danger'
                hold.append(task)
            elif s == 'In Progress':
                task.status_color = 'warning'
                progress.append(task)
            elif s == 'Scheduled':
                task.status_color = 'primary'
                scheduled.append(task)
            else:
                task.status_color = 'secondary'
                hold.append(task) # Cancelled etc
                
        context['kanban_scheduled'] = scheduled
        context['kanban_progress'] = progress
        context['kanban_hold'] = hold
        context['kanban_completed'] = completed[:20] # Limit completed in kanban to recent
        
        # --- CALENDAR PREP ---
        # Group by date for the calendar view
        # Structure: { date_obj: [task1, task2], ... }
        # We need to span the current month (or the requested month)
        calendar_data = {}
        
        # Simple implementation: just map ALL tasks to dates
        # optimize: filter tasks only within strict month window if performance needed
        for t in all_tasks:
            d = t.scheduled_date
            if d not in calendar_data:
                calendar_data[d] = []
            calendar_data[d].append(t)
            
        context['calendar_data'] = calendar_data
        
        # --- KPI COUNTS ---
        context['overdue_count'] = len([t for t in all_tasks if t.status != 'Completed' and t.scheduled_date < today])
        context['today_count'] = len([t for t in all_tasks if t.scheduled_date == today])
        context['progress_count'] = len(progress)
        context['completed_count'] = len(completed) # Total completed in filter scope
        
        # --- WIDGETS ---
        # 1. Technician Load (Active tasks only)
        # We can do this via aggregation on DB side for performance, but python list is fine for small scale
        from django.contrib.auth import get_user_model
        User = get_user_model()
        tech_counts = {}
        for t in scheduled + progress + hold:
            if t.technician:
                uid = t.technician.id
                if uid not in tech_counts:
                    tech_counts[uid] = {'username': t.technician.username, 'active_count': 0}
                tech_counts[uid]['active_count'] += 1
        context['technician_load'] = sorted(tech_counts.values(), key=lambda x: x['active_count'], reverse=True)[:5]

        # 2. Priority Locations (Most issues)
        loc_counts = {}
        for t in hold + progress: # Focus on Overdue/Hold/Progress
            loc = t.location_name
            if loc != "-":
                loc_counts[loc] = loc_counts.get(loc, 0) + 1
        # Convert to list
        sorted_locs = sorted(loc_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        context['priority_locations'] = [{'name': k, 'issue_count': v} for k, v in sorted_locs]

        # Filter Select Options (Hierarchical)
        from assets.models import Location 
        def get_location_tree():
            # Get multiple roots
            roots = Location.objects.filter(parent__isnull=True).prefetch_related('children__children')
            tree = []
            
            def add_node(node, level=0):
                tree.append({
                    'pk': node.pk,
                    'name': node.name,
                    'level': level,
                    'indent': '&nbsp;' * (level * 4)
                })
                for child in node.children.all():
                    add_node(child, level + 1)
            
            for root in roots:
                add_node(root)
            return tree

        context['locations'] = get_location_tree()
        
        # RBAC Check
        user = self.request.user
        context['is_manager'] = user.is_superuser # Simplify for now
        
        return context

# --- Maintenance Schedule Views ---

class MaintenanceScheduleListView(LoginRequiredMixin, ListView):
    model = MaintenanceSchedule
    template_name = 'maintenance/maintenance_schedule_list.html'
    context_object_name = 'schedules'
    ordering = ['next_run_date']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        # 1. RBAC: Determine if user is Manager/Admin
        # Adjust group names as per your system. 'Head IT' was used in Dashboard. 
        # Adding 'Admin', 'Manager' for consistency.
        is_manager = user.is_superuser or user.groups.filter(name__in=['Head IT', 'Admin', 'Manager']).exists()
        
        if not is_manager:
            user_loc = getattr(user, 'location', None)
            if user_loc:
                # User sees schedules for items in their location or sub-locations
                subtree = user_loc.get_descendants(include_self=True)
                qs = qs.filter(
                    Q(asset__location__in=subtree) | 
                    Q(infrastructure__location__in=subtree)
                )
            else:
                # User has no location? Fallback to assigned only or nothing.
                # Showing assigned only is safer.
                qs = qs.filter(assigned_to=user)

        # 2. Location Filtering (Dropdown)
        location_filter = self.request.GET.get('location')
        if location_filter:
            qs = qs.filter(
                Q(asset__location_id=location_filter) | 
                Q(infrastructure__location_id=location_filter)
            )
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # RBAC for Filter Options
        from assets.models import Location
        is_manager = user.is_superuser or user.groups.filter(name__in=['Head IT', 'Admin', 'Manager']).exists()
        
        if is_manager:
            # Show all roots
            roots = Location.objects.filter(parent__isnull=True).prefetch_related('children__children')
        else:
            # Show only user's location as root (or just the subtree)
            user_loc = getattr(user, 'location', None)
            if user_loc:
                roots = [user_loc] # Treat user's loc as the single root for the tree display
            else:
                roots = []

        tree = []
        def add_node(node, level=0):
            tree.append({
                'pk': node.pk,
                'name': node.name,
                'level': level,
                'indent': '&nbsp;' * (level * 4)
            })
            for child in node.children.all():
                add_node(child, level + 1)
        
        for root in roots:
            add_node(root)
            
        context['locations'] = tree
        return context

from .forms import MaintenanceScheduleForm

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class MaintenanceScheduleMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=['Admin', 'Manager', 'IT Support']).exists())

class MaintenanceScheduleCreateView(LoginRequiredMixin, MaintenanceScheduleMixin, CreateView):
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = 'maintenance/maintenance_schedule_form.html'
    success_url = reverse_lazy('maintenance_schedule_list')

    def form_valid(self, form):
        messages.success(self.request, "Maintenance Schedule created successfully.")
        return super().form_valid(form)

class MaintenanceScheduleUpdateView(LoginRequiredMixin, MaintenanceScheduleMixin, UpdateView):
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = 'maintenance/maintenance_schedule_form.html'
    success_url = reverse_lazy('maintenance_schedule_list')

    def form_valid(self, form):
        messages.success(self.request, "Maintenance Schedule updated successfully.")
        return super().form_valid(form)

class MaintenanceScheduleDeleteView(LoginRequiredMixin, MaintenanceScheduleMixin, DeleteView):
    model = MaintenanceSchedule
    template_name = 'maintenance/maintenance_schedule_confirm_delete.html'
    success_url = reverse_lazy('maintenance_schedule_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Maintenance Schedule deleted.")
        return super().delete(request, *args, **kwargs)

from django.shortcuts import get_object_or_404, redirect
from django.db import transaction

@transaction.atomic
def maintenance_schedule_generate(request, pk):
    """
    Manually triggers ticket generation for a specific schedule.
    """
    schedule = get_object_or_404(MaintenanceSchedule, pk=pk)
    
    # Permission check (reuse logic or assume login required/admin)
    if not (request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Manager', 'IT Support']).exists())):
         messages.error(request, "You do not have permission to perform this action.")
         return redirect('maintenance_schedule_list')

    ticket = schedule.create_ticket()
    
    if ticket:
        messages.success(request, f"Maintenance Ticket '{ticket.title}' generated successfully.")
        # Redirect to the ticket update page to see it immediately
        if schedule.asset:
            return redirect('asset_maintenance_update', pk=ticket.pk)
        else:
            return redirect('infra_maintenance_update', pk=ticket.pk)
    else:
        messages.error(request, "Failed to generate ticket. Ensure target (Asset/Infra) is valid.")
        return redirect('maintenance_schedule_list')
