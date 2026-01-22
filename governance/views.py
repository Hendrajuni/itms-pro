from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from .models import (
    DailyLog, DailyLogItem, Project, ProjectTask, FiscalYear, MonthlyReport, BudgetPost
)
from maintenance.models import AssetMaintenance, InfraMaintenance
from tickets.models import Ticket
from .forms import DailyLogForm, DailyLogItemForm, DailyLogItemFormSet
from maintenance.models import AssetMaintenance, InfraMaintenance
from tickets.models import Ticket

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
        queryset = DailyLog.objects.all().select_related('executor').order_by('-date', 'executor')
        
        # Annotate counts for Work Summary
        queryset = queryset.annotate(
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

        # RESTRICTION: Non-superusers (IT Staff) only see their own logs
        if not self.request.user.is_superuser:
            queryset = queryset.filter(executor=self.request.user)

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
        # Get list of users who have logs for the filter dropdown
        # Avoiding circular import if possible, or use string reference if needed, 
        # but importing get_user_model is best practice.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get distinct executors from actual logs to keep list clean
        # or just all users if preferred. Let's do users with logs.
        executor_ids = DailyLog.objects.values_list('executor', flat=True).distinct()
        # Get available years from data
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
        
        context['executors'] = User.objects.filter(id__in=executor_ids).order_by('username')
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

class DailyLogEventsJSON(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Return ALL logs for team visibility
        logs = DailyLog.objects.all().select_related('executor').annotate(
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add quick stats
        context['planning_count'] = Project.objects.filter(status='Planning').count()
        context['progress_count'] = Project.objects.filter(status='In Progress').count()
        context['completed_count'] = Project.objects.filter(status='Completed').count()
        return context

# --- PROJECT VIEWS ---
class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'governance/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tasks = self.object.tasks.all()
        context['all_tasks'] = tasks
        context['my_tasks'] = tasks.filter(assigned_to=self.request.user).exclude(status='Completed')
        context['completed_tasks'] = tasks.filter(status='Completed')
        
        total = tasks.count()
        completed = context['completed_tasks'].count()
        context['progress_percent'] = int((completed / total) * 100) if total > 0 else 0
        return context

class CompleteProjectTaskView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(ProjectTask, pk=pk)
        
        # Permission Check (Manager or Assignee)
        if request.user != task.assigned_to and not request.user.is_superuser and request.user != task.project.manager:
             return redirect('project_detail', pk=task.project.pk)

        # 1. Update Task
        task.status = 'Completed'
        task.completed_at = timezone.now()
        task.save()

        # 2. Update Project Progress
        project = task.project
        total = project.tasks.count()
        done = project.tasks.filter(status='Completed').count()
        project.progress = int((done / total) * 100) if total > 0 else 0
        project.save()

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
            note=f"Completed task for project: {project.name}. {task.description[:50]}"
        )

        return redirect('project_detail', pk=project.pk)
class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    fields = ['name', 'description', 'manager', 'start_date', 'end_date', 'status', 'progress']
    template_name = 'governance/project_form.html'
    success_url = reverse_lazy('project_list')

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
