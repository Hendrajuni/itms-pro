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
    paginate_by = 100

    def get_queryset(self):
        user = self.request.user
        
        # 0. LAZY SCHEDULE EVALUATION
        # Check and run any overdue active schedules automatically
        from django.utils import timezone
        from .models import MaintenanceSchedule
        today = timezone.now().date()
        due_schedules = MaintenanceSchedule.objects.filter(is_active=True, next_run_date__lte=today)
        for schedule in due_schedules:
            schedule.create_ticket(advance_schedule=True)
        
        # 1. Base Query
        asset_tasks = AssetMaintenance.objects.filter(parent__isnull=True).select_related('asset', 'asset__location', 'technician').order_by('scheduled_date')
        infra_tasks = InfraMaintenance.objects.filter(parent__isnull=True).select_related('infrastructure', 'infrastructure__location', 'technician').order_by('scheduled_date')
        
        # 2. RBAC / Location Filtering
        is_manager = user.is_superuser or user.groups.filter(name__in=['Head IT', 'Admin', 'Manager', 'Administrator']).exists()
        
        if not is_manager:
            user_loc = getattr(user, 'location', None)
            if user_loc:
                subtree = user_loc.get_descendants(include_self=True)
                subtree_ids = [loc.id for loc in subtree]
                asset_tasks = asset_tasks.filter(asset__location_id__in=subtree_ids)
                infra_tasks = infra_tasks.filter(infrastructure__location_id__in=subtree_ids)
            else:
                asset_tasks = asset_tasks.filter(technician=user)
                infra_tasks = infra_tasks.filter(technician=user)

        # 3. Filter: Year
        from django.utils import timezone
        default_year = str(timezone.now().year)
        year_filter = self.request.GET.get('year', default_year)
        if year_filter and year_filter.isdigit():
            asset_tasks = asset_tasks.filter(scheduled_date__year=int(year_filter))
            infra_tasks = infra_tasks.filter(scheduled_date__year=int(year_filter))

        # 4. Filter: Type (asset / infra / all)
        type_filter = self.request.GET.get('task_type', '')
        if type_filter == 'asset':
            infra_tasks = InfraMaintenance.objects.none()
        elif type_filter == 'infra':
            asset_tasks = AssetMaintenance.objects.none()

        # 5. Filter: Location
        location_filter = self.request.GET.get('location', '')
        if location_filter and location_filter.isdigit():
            from assets.models import Location
            try:
                loc = Location.objects.get(pk=location_filter)
                desc = loc.get_descendants(include_self=True)
                desc_ids = [l.id for l in desc]
                asset_tasks = asset_tasks.filter(asset__location_id__in=desc_ids)
                infra_tasks = infra_tasks.filter(infrastructure__location_id__in=desc_ids)
            except Location.DoesNotExist:
                pass

        # 6. Filter: Search
        search_q = self.request.GET.get('q', '').strip()
        if search_q:
            asset_tasks = asset_tasks.filter(Q(title__icontains=search_q) | Q(asset__name__icontains=search_q))
            infra_tasks = infra_tasks.filter(Q(title__icontains=search_q) | Q(infrastructure__name__icontains=search_q))

        # 7. Combine
        combined = sorted(chain(asset_tasks, infra_tasks), key=lambda x: x.scheduled_date)
        return combined

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tasks = context['all_tasks']
        
        today = timezone.now().date()
        
        # --- KANBAN BUCKETS ---
        scheduled = []
        progress = []
        hold = []
        completed = []
        
        for task in all_tasks:
            # Decorate with helpers
            if hasattr(task, 'asset') and task.asset:
                task.location_name = task.asset.location.name if task.asset.location else "-"
                task.task_source = 'asset'
            else:
                task.location_name = task.infrastructure.location.name if task.infrastructure and task.infrastructure.location else "-"
                task.task_source = 'infra'
            
            # Calculate subtask progress
            subtask_total = task.subtasks.count()
            subtask_done = task.subtasks.filter(status='Completed').count()
            task.subtask_total = subtask_total
            task.subtask_done = subtask_done
            
            # Checklist progress
            checklist = task.maintenance_checklist or []
            task.checklist_total = len(checklist)
            task.checklist_done = sum(1 for c in checklist if isinstance(c, dict) and c.get('done'))
            
            # Total progress (subtasks + checklist combined)
            total_items = subtask_total + task.checklist_total
            done_items = subtask_done + task.checklist_done
            task.progress_total = total_items
            task.progress_done = done_items
            task.progress_pct = int((done_items / total_items * 100)) if total_items > 0 else 0
                
            # Status Logic
            s = task.status
            if s == 'Completed':
                task.status_color = 'success'
                completed.append(task)
            elif task.scheduled_date < today and s != 'Cancelled':
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
                hold.append(task)
                
        context['kanban_scheduled'] = scheduled
        context['kanban_progress'] = progress
        context['kanban_hold'] = hold
        
        # Completed: limit to reasonable number to prevent lag
        context['kanban_completed'] = completed[:500]
        
        # --- CALENDAR PREP ---
        calendar_data = {}
        for t in all_tasks:
            d = t.scheduled_date
            if d not in calendar_data:
                calendar_data[d] = []
            calendar_data[d].append(t)
        context['calendar_data'] = calendar_data
        
        # --- KPI COUNTS ---
        context['overdue_count'] = len([t for t in all_tasks if t.status != 'Completed' and t.status != 'Cancelled' and t.scheduled_date < today])
        context['today_count'] = len([t for t in all_tasks if t.scheduled_date == today])
        context['progress_count'] = len(progress)
        context['completed_count'] = len(completed)
        context['total_count'] = len(all_tasks)
        
        # --- WIDGETS ---
        # 1. Technician Load
        from django.contrib.auth import get_user_model
        tech_counts = {}
        for t in scheduled + progress + hold:
            if t.technician:
                uid = t.technician.id
                if uid not in tech_counts:
                    tech_counts[uid] = {'username': t.technician.username, 'active_count': 0}
                tech_counts[uid]['active_count'] += 1
        context['technician_load'] = sorted(tech_counts.values(), key=lambda x: x['active_count'], reverse=True)[:5]

        # 2. Priority Locations
        loc_counts = {}
        for t in hold + progress:
            loc = t.location_name
            if loc != "-":
                loc_counts[loc] = loc_counts.get(loc, 0) + 1
        sorted_locs = sorted(loc_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        context['priority_locations'] = [{'name': k, 'issue_count': v} for k, v in sorted_locs]

        # Location Tree for filter
        from assets.models import Location 
        def get_location_tree():
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
        context['is_manager'] = user.is_superuser or user.groups.filter(name__in=['Head IT', 'Admin', 'Manager', 'Administrator']).exists()
        
        # Year options for filter
        import datetime
        current_year = datetime.date.today().year
        context['year_options'] = list(range(current_year - 3, current_year + 2))
        context['current_year'] = current_year
        
        # Preserve filter state
        context['filter_year'] = self.request.GET.get('year', str(current_year))
        context['filter_type'] = self.request.GET.get('task_type', '')
        context['filter_location'] = self.request.GET.get('location', '')
        context['filter_search'] = self.request.GET.get('q', '')
        
        # --- TODAY'S TASKS ---
        context['today_tasks'] = [t for t in all_tasks if t.scheduled_date == today]
        
        # --- SUMMARY STATS (for donut chart) ---
        total = len(all_tasks) or 1  # avoid division by zero
        context['summary_stats'] = {
            'total': len(all_tasks),
            'scheduled': len(scheduled),
            'scheduled_pct': round(len(scheduled) / total * 100),
            'progress': len(progress),
            'progress_pct': round(len(progress) / total * 100),
            'overdue': len(hold),
            'overdue_pct': round(len(hold) / total * 100),
            'completed': len(completed),
            'completed_pct': round(len(completed) / total * 100),
        }
        
        # --- IMPROVED TECHNICIAN LOAD (with percentage bar) ---
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Get all technicians (users in IT Support or assigned to any task)
        all_techs = User.objects.filter(
            Q(groups__name__in=['IT Support', 'Technician']) | 
            Q(assetmaintenance_technician__isnull=False) |
            Q(inframaintenance_technician__isnull=False)
        ).distinct()[:5]
        
        tech_load = []
        max_tasks = max((t.get('active_count', 0) for t in tech_counts.values()), default=1) or 1
        for tech_user in all_techs:
            tc = tech_counts.get(tech_user.id, {'username': tech_user.username, 'active_count': 0})
            tc['pct'] = round(tc['active_count'] / max_tasks * 100)
            tc['initial'] = tech_user.username[0].upper() if tech_user.username else '?'
            tech_load.append(tc)
        context['technician_load'] = sorted(tech_load, key=lambda x: x['active_count'], reverse=True)
        
        # --- RECENT ACTIVITIES (from recent task changes) ---
        recent_asset = AssetMaintenance.objects.select_related('asset', 'technician').order_by('-id')[:5]
        recent_infra = InfraMaintenance.objects.select_related('infrastructure', 'technician').order_by('-id')[:5]
        activities = []
        for t in list(recent_asset) + list(recent_infra):
            target = t.asset.name if hasattr(t, 'asset') and t.asset else (t.infrastructure.name if hasattr(t, 'infrastructure') and t.infrastructure else '-')
            tech_name = t.technician.username if t.technician else 'System'
            if t.status == 'Completed':
                action = f'Task completed - {t.title}'
                icon = 'check-circle'
                color = 'success'
            elif t.status == 'In Progress':
                action = f'Maintenance updated - {t.title}'
                icon = 'sync-alt'
                color = 'warning'
            else:
                action = f'New request - {t.title}'
                icon = 'plus-circle'
                color = 'primary'
            activities.append({
                'action': action,
                'technician': tech_name,
                'date': t.scheduled_date,
                'icon': icon,
                'color': color,
            })
        context['recent_activities'] = sorted(activities, key=lambda x: x['date'], reverse=True)[:6]
        
        # --- MINI CALENDAR DATA ---
        import calendar
        cal = calendar.Calendar(firstweekday=0)  # Monday first
        month_days = cal.monthdayscalendar(today.year, today.month)
        context['cal_weeks'] = month_days
        context['cal_month'] = today.strftime('%B %Y')
        context['cal_today_day'] = today.day
        context['cal_month_num'] = today.month
        context['cal_year'] = today.year
        
        # Days with tasks this month
        task_days = set()
        for t in all_tasks:
            if t.scheduled_date.month == today.month and t.scheduled_date.year == today.year:
                task_days.add(t.scheduled_date.day)
        context['cal_task_days'] = list(task_days)
        
        # --- FULL MONTH AGENDA (Option 1) ---
        full_month_agenda = []
        import datetime
        for week in month_days:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'day': 0, 'is_today': False, 'tasks': []})
                else:
                    d = datetime.date(today.year, today.month, day)
                    day_tasks = [t for t in all_tasks if t.scheduled_date == d]
                    week_data.append({
                        'day': day,
                        'date': d,
                        'is_today': (day == today.day),
                        'tasks': day_tasks
                    })
            full_month_agenda.append(week_data)
        context['full_month_agenda'] = full_month_agenda

        
        return context

# --- AJAX Endpoints ---
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@login_required
@require_POST
def toggle_checklist_item(request):
    """Toggle a checklist item's done status via AJAX"""
    try:
        data = json.loads(request.body)
        task_type = data.get('task_type')  # 'asset' or 'infra'
        task_id = data.get('task_id')
        item_index = data.get('item_index')
        
        if task_type == 'asset':
            task = AssetMaintenance.objects.get(pk=task_id)
        else:
            task = InfraMaintenance.objects.get(pk=task_id)
        
        checklist = task.maintenance_checklist or []
        if 0 <= item_index < len(checklist):
            item = checklist[item_index]
            item['done'] = not item.get('done', False)
            if item['done']:
                item['completed_at'] = timezone.now().isoformat()
                item['completed_by'] = request.user.username
            else:
                item['completed_at'] = None
                item['completed_by'] = None
            
            task.maintenance_checklist = checklist
            task.save(update_fields=['maintenance_checklist'])
            
            done_count = sum(1 for c in checklist if isinstance(c, dict) and c.get('done'))
            total = len(checklist)
            
            return JsonResponse({
                'success': True,
                'done': item['done'],
                'done_count': done_count,
                'total': total,
                'all_done': done_count == total
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def quick_status_update(request):
    """Quickly update task status (start / complete) via AJAX"""
    try:
        data = json.loads(request.body)
        task_type = data.get('task_type')
        task_id = data.get('task_id')
        new_status = data.get('status')
        
        if new_status not in ['Scheduled', 'In Progress', 'Completed', 'Cancelled']:
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        
        if task_type == 'asset':
            task = AssetMaintenance.objects.get(pk=task_id)
        else:
            task = InfraMaintenance.objects.get(pk=task_id)
        
        task.status = new_status
        if new_status == 'Completed':
            # Strict Validation: Check own checklist
            checklist = task.maintenance_checklist or []
            if any(not c.get('done') for c in checklist if isinstance(c, dict)):
                return JsonResponse({'success': False, 'error': 'Terdapat checklist yang belum diselesaikan pada task ini.'}, status=400)
            
            # Strict Validation: Check subtasks and their checklists
            subtasks = task.subtasks.all()
            for st in subtasks:
                if st.status != 'Completed':
                    return JsonResponse({'success': False, 'error': f'Subtask "{st.title}" belum selesai.'}, status=400)
                st_checklist = st.maintenance_checklist or []
                if any(not c.get('done') for c in st_checklist if isinstance(c, dict)):
                    return JsonResponse({'success': False, 'error': f'Terdapat checklist yang belum diselesaikan pada subtask "{st.title}".'}, status=400)
            
            task.completed_date = timezone.now().date()
            
            # Additional Completion Details from Request
            # Timeline
            from django.utils.dateparse import parse_datetime, parse_duration, parse_date
            
            if data.get('actual_start_time'):
                task.actual_start_time = parse_datetime(data.get('actual_start_time'))
            if data.get('actual_completion_time'):
                task.actual_completion_time = parse_datetime(data.get('actual_completion_time'))
                
            # Financial
            try:
                task.labor_cost = float(data.get('labor_cost') or 0)
                task.parts_cost = float(data.get('parts_cost') or 0)
            except ValueError:
                pass
                
            # Vendor
            task.vendor_contact = data.get('vendor_contact', '').strip()
            task.invoice_number = data.get('invoice_number', '').strip()
            if data.get('warranty_expiry_date'):
                task.warranty_expiry_date = parse_date(data.get('warranty_expiry_date'))
                
            # Evaluation
            task.root_cause = data.get('root_cause', '').strip()
            task.resolution_notes = data.get('resolution_notes', '').strip()
            
        task.save()
        
        # Auto-complete parent check: if this is a subtask and all siblings are done
        auto_parent_complete = False
        if task.parent:
            siblings = task.parent.subtasks.all()
            if siblings.count() > 0 and all(s.status == 'Completed' for s in siblings):
                auto_parent_complete = True
        
        return JsonResponse({
            'success': True, 
            'status': new_status,
            'auto_parent_complete': auto_parent_complete,
            'parent_id': task.parent.pk if task.parent else None,
            'parent_title': task.parent.title if task.parent else None,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def task_detail_api(request, task_type, pk):
    """Return task detail as JSON for side panel"""
    try:
        if task_type == 'asset':
            task = AssetMaintenance.objects.select_related('asset', 'asset__location', 'technician').get(pk=pk)
            target_name = task.asset.name
            target_location = task.asset.location.name if task.asset.location else '-'
        else:
            task = InfraMaintenance.objects.select_related('infrastructure', 'infrastructure__location', 'technician').get(pk=pk)
            target_name = task.infrastructure.name
            target_location = task.infrastructure.location.name if task.infrastructure and task.infrastructure.location else '-'
        
        # Subtasks
        subtasks = []
        subtask_done = 0
        subtasks_labor_total = 0
        subtasks_parts_total = 0
        for st in task.subtasks.all().order_by('scheduled_date'):
            is_done = st.status == 'Completed'
            if is_done:
                subtask_done += 1
            st_labor = float(st.labor_cost or 0)
            st_parts = float(st.parts_cost or 0)
            subtasks_labor_total += st_labor
            subtasks_parts_total += st_parts
            subtasks.append({
                'id': st.pk,
                'title': st.title,
                'status': st.status,
                'priority': st.priority,
                'scheduled_date': st.scheduled_date.strftime('%d %b %Y'),
                'technician': st.technician.username if st.technician else None,
                'vendor': st.vendor.name if st.vendor else None,
                'is_done': is_done,
                'labor_cost': st_labor,
                'parts_cost': st_parts,
                'cost': float(st.cost or 0),
            })
        
        # Combined progress
        checklist = task.maintenance_checklist or []
        cl_done = sum(1 for c in checklist if isinstance(c, dict) and c.get('done'))
        total_items = len(subtasks) + len(checklist)
        done_items = subtask_done + cl_done
        progress_pct = round(done_items / total_items * 100) if total_items > 0 else 0
        
        # Parent info
        parent_info = None
        if task.parent:
            parent_info = {
                'id': task.parent.pk,
                'title': task.parent.title,
                'code': task.parent.maintenance_code,
            }
        
        return JsonResponse({
            'id': task.pk,
            'task_type': task_type,
            'code': task.maintenance_code,
            'title': task.title,
            'priority': task.priority,
            'status': task.status,
            'maintenance_type': task.maintenance_type,
            'scheduled_date': task.scheduled_date.strftime('%d %b %Y'),
            'completed_date': task.completed_date.strftime('%d %b %Y') if task.completed_date else None,
            'technician': task.technician.username if task.technician else None,
            'target_name': target_name,
            'target_location': target_location,
            'notes': task.notes,
            'checklist': checklist,
            'subtasks': subtasks,
            'subtask_total': len(subtasks),
            'subtask_done': subtask_done,
            'progress_pct': progress_pct,
            'progress_done': done_items,
            'progress_total': total_items,
            'parent': parent_info,
            'photo_before': task.photo_before.url if task.photo_before else None,
            'photo_after': task.photo_after.url if task.photo_after else None,
            
            # --- New Evaluation Fields ---
            'actual_start_time': task.actual_start_time.strftime('%Y-%m-%d %H:%M') if task.actual_start_time else None,
            'actual_completion_time': task.actual_completion_time.strftime('%Y-%m-%d %H:%M') if task.actual_completion_time else None,
            'labor_cost': float(task.labor_cost),
            'parts_cost': float(task.parts_cost),
            'total_cost': float(task.cost),
            'vendor_contact': task.vendor_contact,
            'invoice_number': task.invoice_number,
            'warranty_expiry_date': task.warranty_expiry_date.strftime('%d %b %Y') if task.warranty_expiry_date else None,
            'root_cause': task.root_cause,
            'resolution_notes': task.resolution_notes,
            
            # --- Cost Aggregation ---
            'subtasks_labor_total': subtasks_labor_total,
            'subtasks_parts_total': subtasks_parts_total,
            'subtasks_cost_total': sum(float(st.get('cost', 0)) for st in subtasks),
            'grand_labor_total': float(task.labor_cost or 0) + subtasks_labor_total,
            'grand_parts_total': float(task.parts_cost or 0) + subtasks_parts_total,
            'grand_total': float(task.cost or 0) + sum(float(st.get('cost', 0)) for st in subtasks),
            
            'edit_url': reverse_lazy('asset_maintenance_update', kwargs={'pk': task.pk}).__str__() if task_type == 'asset' else reverse_lazy('infra_maintenance_update', kwargs={'pk': task.pk}).__str__(),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

@login_required
@require_POST
def add_subtask(request):
    """Create a subtask inline from the side panel via AJAX"""
    try:
        data = json.loads(request.body)
        task_type = data.get('task_type')  # 'asset' or 'infra'
        parent_id = data.get('parent_id')
        title = data.get('title', '').strip()
        technician_id = data.get('technician_id')
        scheduled_date_str = data.get('scheduled_date')
        priority = data.get('priority', 'Medium')
        estimated_cost = data.get('estimated_cost', 0)
        
        # Parse estimated cost
        try:
            estimated_cost = float(estimated_cost) if estimated_cost else 0
        except (ValueError, TypeError):
            estimated_cost = 0
        
        # Parse scheduled_date string to date object
        parsed_date = None
        if scheduled_date_str:
            from datetime import datetime as dt
            try:
                parsed_date = dt.strptime(scheduled_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                parsed_date = None
        
        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if task_type == 'asset':
            parent = AssetMaintenance.objects.get(pk=parent_id)
            subtask = AssetMaintenance(
                title=title,
                asset=parent.asset,
                parent=parent,
                maintenance_type=parent.maintenance_type,
                priority=priority,
                scheduled_date=parsed_date or parent.scheduled_date,
                technician=User.objects.filter(pk=technician_id).first() if technician_id else parent.technician,
                status='Scheduled',
                labor_cost=estimated_cost,
            )
        else:
            parent = InfraMaintenance.objects.get(pk=parent_id)
            subtask = InfraMaintenance(
                title=title,
                infrastructure=parent.infrastructure,
                parent=parent,
                maintenance_type=parent.maintenance_type,
                priority=priority,
                scheduled_date=parsed_date or parent.scheduled_date,
                technician=User.objects.filter(pk=technician_id).first() if technician_id else parent.technician,
                status='Scheduled',
                labor_cost=estimated_cost,
            )
        
        subtask.save()
        subtask.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'subtask': {
                'id': subtask.pk,
                'title': subtask.title,
                'code': subtask.maintenance_code,
                'status': subtask.status,
                'priority': subtask.priority,
                'technician': subtask.technician.username if subtask.technician else None,
                'scheduled_date': subtask.scheduled_date.strftime('%d %b %Y'),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# --- Maintenance Schedule Views ---

class MaintenanceScheduleListView(LoginRequiredMixin, ListView):
    model = MaintenanceSchedule
    template_name = 'maintenance/maintenance_schedule_list.html'
    context_object_name = 'schedules'
    ordering = ['next_run_date']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        is_manager = user.is_superuser or user.groups.filter(name__in=['Head IT', 'Admin', 'Manager']).exists()
        
        if not is_manager:
            user_loc = getattr(user, 'location', None)
            if user_loc:
                subtree = user_loc.get_descendants(include_self=True)
                qs = qs.filter(
                    Q(asset__location__in=subtree) | 
                    Q(infrastructure__location__in=subtree)
                )
            else:
                qs = qs.filter(assigned_to=user)

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
        
        from assets.models import Location
        is_manager = user.is_superuser or user.groups.filter(name__in=['Head IT', 'Admin', 'Manager']).exists()
        
        if is_manager:
            roots = Location.objects.filter(parent__isnull=True).prefetch_related('children__children')
        else:
            user_loc = getattr(user, 'location', None)
            if user_loc:
                roots = [user_loc]
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
    
    if not (request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Manager', 'IT Support']).exists())):
         messages.error(request, "You do not have permission to perform this action.")
         return redirect('maintenance_schedule_list')

    ticket = schedule.create_ticket()
    
    if ticket:
        messages.success(request, f"Maintenance Ticket '{ticket.title}' generated successfully.")
        if schedule.asset:
            return redirect('asset_maintenance_update', pk=ticket.pk)
        else:
            return redirect('infra_maintenance_update', pk=ticket.pk)
    else:
        messages.error(request, "Failed to generate ticket. Ensure target (Asset/Infra) is valid.")
        return redirect('maintenance_schedule_list')


@login_required
def maintenance_report(request, task_type, pk):
    """Print-ready maintenance completion report"""
    import qrcode
    import base64
    from io import BytesIO
    from decimal import Decimal
    
    if task_type == 'asset':
        task = AssetMaintenance.objects.select_related('asset', 'asset__location', 'technician', 'vendor').get(pk=pk)
        target_name = task.asset.name
        target_code = task.asset.asset_tag if hasattr(task.asset, 'asset_tag') else str(task.asset.pk)
        target_location = task.asset.location.name if task.asset.location else '-'
    else:
        task = InfraMaintenance.objects.select_related('infrastructure', 'infrastructure__location', 'technician', 'vendor').get(pk=pk)
        target_name = task.infrastructure.name
        target_code = task.infrastructure.infra_id if hasattr(task.infrastructure, 'infra_id') else str(task.infrastructure.pk)
        target_location = task.infrastructure.location.name if task.infrastructure and task.infrastructure.location else '-'
    
    # Subtasks with costs
    subtasks = list(task.subtasks.all().select_related('technician', 'vendor').order_by('scheduled_date'))
    subtasks_labor = sum(float(st.labor_cost or 0) for st in subtasks)
    subtasks_parts = sum(float(st.parts_cost or 0) for st in subtasks)
    subtasks_cost_total = sum(float(st.cost or 0) for st in subtasks)
    
    grand_labor = float(task.labor_cost or 0) + subtasks_labor
    grand_parts = float(task.parts_cost or 0) + subtasks_parts
    grand_total = float(task.cost or 0) + subtasks_cost_total
    
    # Checklist - format dates
    from datetime import datetime as dt
    checklist = task.maintenance_checklist or []
    checklist_done = 0
    for c in checklist:
        if isinstance(c, dict):
            if c.get('done'):
                checklist_done += 1
            # Format the completed_at date
            raw_date = c.get('completed_at', '')
            if raw_date and isinstance(raw_date, str):
                try:
                    parsed = dt.fromisoformat(raw_date.replace('Z', '+00:00'))
                    c['completed_at_formatted'] = parsed.strftime('%d %b %Y')
                except (ValueError, TypeError):
                    c['completed_at_formatted'] = raw_date[:10] if len(raw_date) > 10 else raw_date
            else:
                c['completed_at_formatted'] = '-'
    
    # Duration calculation
    duration_str = '-'
    if task.actual_start_time and task.actual_completion_time:
        diff = task.actual_completion_time - task.actual_start_time
        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days} hari")
        if hours > 0:
            parts.append(f"{hours} jam")
        if minutes > 0:
            parts.append(f"{minutes} menit")
        duration_str = ' '.join(parts) if parts else '< 1 menit'
    
    # QR Code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(f"/maintenance/report/{task_type}/{pk}/")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"
    
    context = {
        'task': task,
        'task_type': task_type,
        'target_name': target_name,
        'target_code': target_code,
        'target_location': target_location,
        'subtasks': subtasks,
        'checklist': checklist,
        'checklist_done': checklist_done,
        'checklist_total': len(checklist),
        'grand_labor': grand_labor,
        'grand_parts': grand_parts,
        'grand_total': grand_total,
        'duration_str': duration_str,
        'qr_base64': qr_base64,
    }
    
    return render(request, 'maintenance/maintenance_report.html', context)


@require_POST
def toggle_schedule_active(request):
    import json
    from django.http import JsonResponse
    try:
        data = json.loads(request.body)
        schedule_id = data.get('schedule_id')
        is_active = data.get('is_active')
        
        schedule = MaintenanceSchedule.objects.get(pk=schedule_id)
        schedule.is_active = is_active
        schedule.save()
        
        return JsonResponse({'status': 'success', 'is_active': schedule.is_active})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def schedule_history_api(request, pk):
    from django.http import JsonResponse
    from .models import MaintenanceSchedule, AssetMaintenance, InfraMaintenance
    try:
        schedule = MaintenanceSchedule.objects.get(pk=pk)
        
        # Determine prefix. create_ticket sets title like "Title - DD/MM/YYYY"
        prefix = f"{schedule.title} -"
        
        # Query both
        asset_tasks = list(AssetMaintenance.objects.filter(title__startswith=prefix).order_by('-completed_date', '-scheduled_date'))
        infra_tasks = list(InfraMaintenance.objects.filter(title__startswith=prefix).order_by('-completed_date', '-scheduled_date'))
        
        # Combine and sort
        all_tasks = asset_tasks + infra_tasks
        # Sort by completed_date (if completed) or scheduled_date
        all_tasks.sort(key=lambda x: x.completed_date or x.scheduled_date or x.created_at, reverse=True)
        
        history = []
        for t in all_tasks:
            date_str = t.completed_date.strftime('%d %b %Y') if t.completed_date else t.scheduled_date.strftime('%d %b %Y')
            history.append({
                'id': t.pk,
                'title': t.title,
                'status': t.status,
                'date': date_str,
                'type': 'Asset' if isinstance(t, AssetMaintenance) else 'Infra'
            })
            
        return JsonResponse({'status': 'success', 'history': history})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
