from django.shortcuts import render, get_object_or_404, redirect
from django import forms
from django.db import transaction
from django.db.models import Count, Q, OuterRef, Subquery, IntegerField, F, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from .models import (
    DailyLog, DailyLogItem, Project, ProjectTask, FiscalYear, MonthlyReport, BudgetPost, DisposalRequest
)
from maintenance.models import AssetMaintenance, InfraMaintenance
from tickets.models import Ticket
from .forms import DailyLogForm, DailyLogItemForm, DailyLogItemFormSet
from maintenance.models import AssetMaintenance, InfraMaintenance
from tickets.models import Ticket

# --- Helper for Visibility Scope ---
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, permission_required
def get_visible_daily_logs(user):
    """
    Returns a QuerySet of DailyLogs visible to the user based on Role/Location.
    Policy:
    1. Superuser / Head IT: All logs.
    2. Manager: Logs from own location AND descendants (hierarchical).
    3. Staff: Logs from own location ONLY (collaborative).
    """
    qs = DailyLog.objects.all().select_related('executor', 'executor__location').order_by('-date', 'executor')
    
    # 1. Global Viewers
    if user.is_superuser or user.groups.filter(name__in=['Head IT', 'Director']).exists():
        return qs

    # Check User Location
    if not hasattr(user, 'location') or not user.location:
        # Fallback: If no location assigned, strict to own logs only
        return qs.filter(executor=user)

    # 2. Managers (Hierarchical)
    if user.groups.filter(name='Manager').exists():
        # Get location subtree
        user_loc = user.location
        subtree = user_loc.get_descendants(include_self=True)
        return qs.filter(executor__location__in=subtree)

    # 3. Standard Staff (Collaborative - Same Branch)
    # Filter logs where executor is in the SAME location as the user
    return qs.filter(executor__location=user.location)

# --- Daily Log Views ---

class DailyLogListView(LoginRequiredMixin, ListView):
    model = DailyLog
    template_name = 'governance/dailylog_list.html'
    context_object_name = 'logs'
    ordering = ['-date']

    def get_template_names(self):
        if self.request.GET.get('view') == 'calendar':
            return ['governance/dailylog_calendar.html']
        return super().get_template_names()

    def get_queryset(self):
        # Use Helper for Base Scope
        queryset = get_visible_daily_logs(self.request.user)
        
        # Subquery to count resolved tickets for the executor on the specific date
        tickets_resolved_qs = Ticket.objects.filter(
            assigned_to=OuterRef('executor'),
            resolved_at__date=OuterRef('date')
        ).values('assigned_to').annotate(cnt=Count('id')).values('cnt')

        # Annotate counts for Work Summary
        queryset = queryset.annotate(
            manual_ticket_count=Count('items', filter=Q(items__content_type__model='ticket')),
            auto_ticket_count=Coalesce(Subquery(tickets_resolved_qs[:1], output_field=IntegerField()), 0),
            maintenance_count=Count('items', filter=
                Q(items__related_asset__isnull=False) | 
                Q(items__related_infra__isnull=False) |
                Q(items__content_type__model__in=['assetmaintenance', 'inframaintenance'])
            ),
            project_count=Count('items', filter=Q(items__category='Development')),
            general_count=Count('items', filter=
                ~Q(items__content_type__model='ticket') & 
                ~Q(items__content_type__model__in=['assetmaintenance', 'inframaintenance']) &
                ~Q(items__category='Development') &
                Q(items__related_asset__isnull=True) & 
                Q(items__related_infra__isnull=True)
            )
        ).annotate(
            ticket_count=F('manual_ticket_count') + F('auto_ticket_count')
        )

        # Date Filtering (Month/Year)
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        
        if month:
            queryset = queryset.filter(date__month=month)
        if year:
            queryset = queryset.filter(date__year=year)

        # Filter by Executor (for admins/filtering)
        executor_id = self.request.GET.get('executor')
        if executor_id:
            queryset = queryset.filter(executor_id=executor_id)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Filter Dropdown: Only show executors present in the visible QuerySet
        # This prevents seeing users from other regions in the dropdown
        visible_logs = get_visible_daily_logs(self.request.user)
        visible_executor_ids = visible_logs.values_list('executor', flat=True).distinct()
        
        context['executors'] = User.objects.filter(id__in=visible_executor_ids).order_by('username')
        
        from django.db.models.functions import ExtractYear
        available_years = DailyLog.objects.annotate(year=ExtractYear('date')).values_list('year', flat=True).distinct().order_by('-year')
        
        context['months'] = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
        context['years'] = available_years
        
        context['selected_month'] = int(self.request.GET.get('month')) if self.request.GET.get('month') else ''
        context['selected_year'] = int(self.request.GET.get('year')) if self.request.GET.get('year') else ''
        context['selected_executor'] = self.request.GET.get('executor', '')
        return context

class DailyLogCreateView(LoginRequiredMixin, CreateView):
    model = DailyLog
    form_class = DailyLogForm
    template_name = 'governance/dailylog_form.html'
    success_url = reverse_lazy('dailylog_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Restrict executor field for non-superusers (IT Staff)
        if not self.request.user.is_superuser:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            form.fields['executor'].queryset = User.objects.filter(pk=self.request.user.pk)
            form.fields['executor'].initial = self.request.user
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = DailyLogItemFormSet(self.request.POST)
        else:
            context['items'] = DailyLogItemFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        if items.is_valid():
            with transaction.atomic():
                if not form.cleaned_data.get('executor'):
                    form.instance.executor = self.request.user
                self.object = form.save()
                items.instance = self.object
                items.save()
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class DailyLogUpdateView(LoginRequiredMixin, UpdateView):
    model = DailyLog
    form_class = DailyLogForm
    template_name = 'governance/dailylog_form.html'
    success_url = reverse_lazy('dailylog_list')

    def get_queryset(self):
        # Restrict editing to own logs unless superuser
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            qs = qs.filter(executor=self.request.user)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.request.user.is_superuser:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            form.fields['executor'].queryset = User.objects.filter(pk=self.request.user.pk)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = DailyLogItemFormSet(self.request.POST, instance=self.object)
        else:
            context['items'] = DailyLogItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        if items.is_valid():
            with transaction.atomic():
                self.object = form.save()
                items.instance = self.object
                items.save()
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class DailyLogBulkApproveView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
    def post(self, request, *args, **kwargs):
        log_ids = request.POST.getlist('log_ids')
        if log_ids:
            with transaction.atomic():
                logs = DailyLog.objects.filter(id__in=log_ids).exclude(status='Approved')
                count = logs.count()
                logs.update(
                    status='Approved'
                )
            if count > 0:
                messages.success(request, f"Successfully approved {count} daily logs.")
            else:
                messages.info(request, "No eligible logs were selected for approval.")
        else:
            messages.warning(request, "No logs selected.")
            
        return redirect('dailylog_list')

class DailyLogEventsJSON(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # CORRECTED: Use Helper to enforce Location Permissions
        logs = get_visible_daily_logs(request.user)
        
        # Annotate counts for summary logic
        logs = logs.annotate(
            ticket_count=Count('items', filter=Q(items__content_type__model='ticket')),
            maintenance_count=Count('items', filter=
                Q(items__related_asset__isnull=False) | 
                Q(items__related_infra__isnull=False) |
                Q(items__content_type__model__in=['assetmaintenance', 'inframaintenance'])
            ),
            general_count=Count('items', filter=
                ~Q(items__content_type__model='ticket') & 
                ~Q(items__content_type__model__in=['assetmaintenance', 'inframaintenance']) &
                Q(items__related_asset__isnull=True) & 
                Q(items__related_infra__isnull=True)
            )
        )
        
        events = []
        for log in logs:
            # Color coding (Strict Logic)
            if log.work_location == 'SITE':
                color = '#fd7e14' # Orange
            elif log.work_location == 'REMOTE':
                color = '#198754' # Green
            else:
                color = '#0d6efd' # HO (Blue)

            # Summary HTML for tooltip
            summary_html = ""
            if log.general_count > 0: summary_html += f'<span class="badge bg-light text-dark border me-1"><i class="fas fa-tasks text-secondary"></i> {log.general_count}</span>'
            if log.maintenance_count > 0: summary_html += f'<span class="badge bg-light text-dark border me-1"><i class="fas fa-tools text-warning"></i> {log.maintenance_count}</span>'
            if log.ticket_count > 0: summary_html += f'<span class="badge bg-light text-dark border me-1"><i class="fas fa-ticket-alt text-danger"></i> {log.ticket_count}</span>'

            can_edit = request.user.is_superuser or request.user == log.executor

            # Avatar Logic (Safe access)
            avatar_url = '/static/img/default-avatar.png'
            if hasattr(log.executor, 'profile') and log.executor.profile.photo:
                avatar_url = log.executor.profile.photo.url

            # Calculate Initials
            initials = "U"
            if log.executor.first_name and log.executor.last_name:
                initials = f"{log.executor.first_name[0]}{log.executor.last_name[0]}"
            elif log.executor.first_name:
                initials = log.executor.first_name[:2]
            elif log.executor.username:
                initials = log.executor.username[:2]
            
            initials = initials.upper()

            events.append({
                'id': log.id,
                'title': log.executor.first_name or log.executor.username,
                'start': log.date.isoformat(),
                'backgroundColor': color,
                'borderColor': color,
                'extendedProps': {
                    'location': log.get_work_location_display(),
                    'type': log.work_location, # For filtering: HO, SITE, REMOTE
                    'avatar': avatar_url,
                    'initials': initials,
                    'summary_html': summary_html,
                    'can_edit': can_edit,
                    'edit_url': str(reverse_lazy('dailylog_update', kwargs={'pk': log.pk})) if can_edit else '#'
                }
            })
            
        return JsonResponse(events, safe=False)

class DailyLogDetailView(LoginRequiredMixin, DetailView):
    model = DailyLog
    template_name = 'governance/dailylog_detail.html'
    context_object_name = 'log'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object.executor
        log_date = self.object.date
        
        # 1. Manual Items
        context['manual_items'] = self.object.items.all()
        
        # 2. Asset Maintenance (Auto-detected)
        # Query AssetMaintenance where technician=user AND scheduled_date=log.date
        # Or completed_date? User said "date=log.date". 
        # Typically daily log reflects work done on that day.
        # Checking both strict equality.
        context['asset_work'] = AssetMaintenance.objects.filter(
            technician=user, 
            scheduled_date=log_date
        )
        
        # 3. Infra Maintenance
        context['infra_work'] = InfraMaintenance.objects.filter(
            technician=user, 
            scheduled_date=log_date
        )
        
        # 4. Tickets Resolved
        # Query Ticket where assigned_to=user AND resolved_at date matches log.date
        # tickets resolved TODAY (or log date)
        context['tickets'] = Ticket.objects.filter(
            assigned_to=user,
            resolved_at__date=log_date
        )
        
        return context

class DailyLogPrintView(DailyLogDetailView):
    template_name = 'governance/dailylog_print.html'

class DailyLogItemCreateView(LoginRequiredMixin, CreateView):
    model = DailyLogItem
    form_class = DailyLogItemForm
    template_name = 'governance/dailylogitem_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.log = get_object_or_404(DailyLog, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.log = self.log
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('dailylog_detail', kwargs={'pk': self.log.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['log'] = self.log
        return context

# --- Stub Views for Governance Modules ---
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum

class FiscalDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'governance/fiscal_dashboard.html'

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.groups.filter(name='Manager').exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Available Years for Dropdown
        available_years = FiscalYear.objects.values_list('year', flat=True).order_by('-year')
        context['available_years'] = available_years
        
        # Determine Year to Show
        year_param = self.request.GET.get('year')
        if year_param:
            fiscal_year = FiscalYear.objects.filter(year=year_param).first()
        else:
            fiscal_year = FiscalYear.objects.order_by('-year').first()
            
        context['fiscal_year'] = fiscal_year
        
        if fiscal_year:
            # Aggregate Budget Data
            budget_posts = fiscal_year.budget_posts.all()
            total_allocated = budget_posts.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
            
            # 1. By Category
            by_category = []
            for cat_code, cat_name in BudgetPost.CATEGORY_CHOICES:
                cat_total = budget_posts.filter(category=cat_code).aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
                by_category.append({
                    'name': cat_name,
                    'total': cat_total,
                    'percent': int((cat_total / total_allocated) * 100) if total_allocated > 0 else 0
                })
            
            # 2. By Department
            # Note: We need to handle posts with no department
            dept_data = budget_posts.values('department__name').annotate(total=Sum('allocated_amount')).order_by('-total')
            by_department = []
            for item in dept_data:
                name = item['department__name'] or "General / Unassigned"
                total = item['total'] or 0
                by_department.append({
                    'name': name,
                    'total': total,
                    'percent': int((total / total_allocated) * 100) if total_allocated > 0 else 0
                })

            # 3. By Location
            loc_data = budget_posts.values('location__name').annotate(total=Sum('allocated_amount')).order_by('-total')
            by_location = []
            for item in loc_data:
                name = item['location__name'] or "General / Unassigned"
                total = item['total'] or 0
                by_location.append({
                    'name': name,
                    'total': total,
                    'percent': int((total / total_allocated) * 100) if total_allocated > 0 else 0
                })
            
            context['total_allocated'] = total_allocated
            context['by_category'] = by_category
            context['by_department'] = by_department
            context['by_location'] = by_location
            
            # Mock "Spent" Data 
            context['total_spent'] = 0 
            context['total_remaining'] = total_allocated 
            
        return context

class MonthlyReportListView(LoginRequiredMixin, TemplateView):
    template_name = 'core/under_construction.html'

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'governance/project_list.html'
    context_object_name = 'projects'
    ordering = ['-start_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('location', 'vendor', 'manager')
        year = self.request.GET.get('year')
        if year and year != 'all':
             queryset = queryset.filter(start_date__year=year)
        
        location_id = self.request.GET.get('location')
        if location_id and location_id != 'all':
            queryset = queryset.filter(location_id=location_id)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add quick stats
        context['planning_count'] = Project.objects.filter(status='Planning').count()
        context['progress_count'] = Project.objects.filter(status='In Progress').count()
        context['completed_count'] = Project.objects.filter(status='Completed').count()
        
        # Years for filter
        from assets.models import Location
        context['years'] = Project.objects.dates('start_date', 'year', order='DESC')
        context['selected_year'] = self.request.GET.get('year', 'all')
        
        # Location filter
        context['location_list'] = Location.objects.all()
        context['selected_location'] = self.request.GET.get('location', 'all')
        
        return context

# --- PROJECT VIEWS ---
class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'governance/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        tasks = project.tasks.select_related('assigned_to').all()
        
        # 1. Kanban Buckets
        context['tasks_pending'] = tasks.filter(status='Pending')
        context['tasks_progress'] = tasks.filter(status='In Progress')
        context['tasks_completed'] = tasks.filter(status='Completed')
        
        # 2. My Active Tasks (for quick action)
        context['my_tasks'] = tasks.filter(assigned_to=self.request.user).exclude(status='Completed')
        
        # 3. Team Members (Distinct assignees)
        # Using a set comprehension to get unique users, excluding None
        team_members = {t.assigned_to for t in tasks if t.assigned_to}
        # Add manager if not already in list
        if project.manager:
            team_members.add(project.manager)
        context['team_members'] = team_members
        
        # 4. Progress & Timeline
        total = tasks.count()
        completed = context['tasks_completed'].count()
        context['progress_percent'] = int((completed / total) * 100) if total > 0 else 0
        
        today = timezone.now().date()
        if project.end_date and project.end_date >= today:
            context['days_remaining'] = (project.end_date - today).days
        else:
            context['days_remaining'] = 0
            
        # 5. Financials (Placeholder for now, using BudgetPost if linked)
        context['budget_allocated'] = project.budget.allocated_amount if project.budget else 0
        # Future: Calculate actual expenses
        
        return context

@method_decorator(transaction.atomic, name='dispatch')
class CompleteProjectTaskView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(ProjectTask, pk=pk)
        
        # Permission Check (Manager or Assignee)
        if request.user != task.assigned_to and not request.user.is_superuser and request.user != task.project.manager:
             return redirect('project_detail', pk=task.project.pk)

        # 1. Update Task
        task.status = 'Completed'
        task.completed_at = timezone.now()
        
        # Capture Feedback Data
        task.actual_hours = request.POST.get('actual_hours') or None
        task.completion_difficulty = request.POST.get('completion_difficulty')
        task.completion_note = request.POST.get('completion_note', '')
        
        task.save()

        # 2. Update Project Progress
        # Logic handled by ProjectTask.save() signal/override now.
        # project.update_progress() # triggered automatically

        # 3. AUTO-LOG LOGIC
        # Find/Create Log
        today = timezone.now().date()
        log, created = DailyLog.objects.get_or_create(
            executor=request.user,
            date=today,
            defaults={'work_location': 'HO'} # Default to HO
        )
        
        # Create Log Item
        DailyLogItem.objects.create(
            log=log,
            task_name=f"Project Task: {task.name}",
            category='Development',
            start_time=timezone.now().time(), # Approximation
            end_time=timezone.now().time(),
            status='Completed',
            note=f"Completed task: {task.name}. {task.completion_note[:200]}"
        )

        return redirect('project_detail', pk=task.project.pk)
class ProjectCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Project
    fields = ['name', 'category', 'description', 'manager', 'location', 'vendor', 'start_date', 'end_date', 'budget']
    template_name = 'governance/project_form.html'
    success_url = reverse_lazy('project_list')

    def test_func(self):
        # Allow Admin, Manager, and IT Staff (custom group check) to create projects
        # Usually project creation is restricted.
        return self.request.user.is_superuser or self.request.user.groups.filter(name__in=['Admin', 'Manager']).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'New Project'
        from .forms import ProjectTaskFormSet
        if self.request.POST:
            context['tasks'] = ProjectTaskFormSet(self.request.POST)
        else:
            context['tasks'] = ProjectTaskFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        tasks = context['tasks']
        self.object = form.save()
        if tasks.is_valid():
            tasks.instance = self.object
            tasks.save()
        return super().form_valid(form)

class ProjectUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Project
    fields = ['name', 'category', 'description', 'manager', 'location', 'vendor', 'start_date', 'end_date', 'status', 'budget'] # Removed progress (auto-calculated)
    template_name = 'governance/project_form.html'
    success_url = reverse_lazy('project_list')

    def test_func(self):
        user = self.request.user
        # Strict: Only Admin, Superuser, or the Manager assigned to the project can edit the project details.
        # Regular IT Staff cannot edit project details.
        if user.is_superuser: return True
        if user.groups.filter(name__in=['Admin', 'Manager']).exists(): return True
        if self.get_object().manager == user: return True
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit Project'
        from .forms import ProjectTaskFormSet
        if self.request.POST:
            context['tasks'] = ProjectTaskFormSet(self.request.POST, instance=self.object)
        else:
            context['tasks'] = ProjectTaskFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        tasks = context['tasks']
        with transaction.atomic():
            self.object = form.save()
            if tasks.is_valid():
                tasks.instance = self.object
                tasks.save()
        return super().form_valid(form)

# --- DISPOSAL VIEWS ---
class DisposalListView(LoginRequiredMixin, ListView):
    model = DisposalRequest
    template_name = 'governance/disposal_list.html'
    context_object_name = 'requests'
    ordering = ['-request_date']

    def get_queryset(self):
        qs = super().get_queryset().select_related('asset', 'requested_by', 'approved_by')
        
        # Filter by User Role
        if not self.request.user.is_superuser:
            qs = qs.filter(requested_by=self.request.user)
            
        # Filter by Status (URL Param)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
            
        return qs
        form.fields['start_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        form.fields['end_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Project'
        from .forms import ProjectTaskFormSet
        if self.request.POST:
            context['tasks'] = ProjectTaskFormSet(self.request.POST)
        else:
            context['tasks'] = ProjectTaskFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        tasks = context['tasks']
        with transaction.atomic():
            self.object = form.save()
            if tasks.is_valid():
                tasks.instance = self.object
                tasks.save()
        return super().form_valid(form)

@method_decorator(login_required, name='dispatch')
class ProjectDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Project
    template_name = 'governance/project_confirm_delete.html'
    success_url = reverse_lazy('project_list')
    context_object_name = 'project'

    def test_func(self):
        # Only Allow Admin or Superuser
        return self.request.user.is_superuser or self.request.user.groups.filter(name='Admin').exists()

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to delete projects.")
        return redirect('project_list')

# Disposal Request Print View
class DisposalRequestPrintView(LoginRequiredMixin, DetailView):
    model = DisposalRequest
    template_name = 'governance/print_disposal.html'
    context_object_name = 'disposal'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_date'] = timezone.now().date()
        return context

from .forms import DisposalRequestForm
from assets.models import Asset

class DisposalRequestCreateView(LoginRequiredMixin, CreateView):
    model = DisposalRequest
    form_class = DisposalRequestForm
    template_name = 'governance/disposal_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(Asset, pk=self.kwargs['asset_pk'])
        # Optional: Check if already has pending request or disposed
        if hasattr(self.asset, 'disposalrequest'):
             pending = self.asset.disposalrequest
             if pending.status == 'Pending':
                  messages.warning(request, f"This asset already has a pending disposal request.")
                  return redirect('asset_detail', pk=self.asset.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.asset = self.asset
        form.instance.requested_by = self.request.user
        messages.success(self.request, "Disposal request submitted successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.asset.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.asset
        context['page_title'] = f"Request Disposal: {self.asset.asset_code}"
        return context

class DisposalRequestDetailView(LoginRequiredMixin, DetailView):
    model = DisposalRequest
    template_name = 'governance/disposal_detail.html'
    context_object_name = 'request'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Permission Check
        if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administrator', 'Manager']).exists()):
             messages.error(request, "You do not have permission to approve/reject requests.")
             return redirect('disposal_list')

        action = request.POST.get('action')
        if action == 'approve':
            with transaction.atomic():
                self.object.status = 'Approved'
                self.object.approved_by = request.user
                self.object.approval_date = timezone.now()
                self.object.save()
                
                # Update Asset Status
                asset = self.object.asset
                asset.status = 'DISPOSED'
                asset.save()
                
            messages.success(request, f"Disposal request for {asset.name} APPROVED. Asset status updated to Disposed.")
            
        elif action == 'reject':
            self.object.status = 'Rejected'
            # self.object.rejection_reason = ... (if we had a field)
            self.object.save()
            messages.warning(request, "Disposal request rejected.")
            
        return redirect('disposal_list')
