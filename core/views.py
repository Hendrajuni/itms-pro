from django.shortcuts import render, redirect
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Count, Sum
from django.db.models.functions import ExtractYear, ExtractMonth
from django.utils import timezone
from datetime import timedelta
from assets.models import Asset, Contract, Software
from maintenance.models import AssetMaintenance, InfraMaintenance
from django.db.models import Q
from django.contrib.auth import get_user_model
User = get_user_model()
from tickets.models import Ticket
from network.models import NetworkNode
from governance.models import DailyLog
from django.utils.decorators import method_decorator

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        user = self.request.user
        if user.is_superuser or user.groups.filter(name='Administrator').exists():
            return '/dashboard/admin/'
        elif user.groups.filter(name='IT Support').exists():
            return '/dashboard/it/'
        else:
            return '/dashboard/staff/'

def get_dashboard_stats(user):
    """
    Context helper to fetch dashboard statistics based on role.
    """
    from datetime import datetime, timedelta
    from django.db.models import Q
    stats = {}
    
    # 1. Staff Stats
    # Always relevant or if user is staff
    stats['my_tickets_count'] = Ticket.objects.filter(created_by=user).exclude(status='Closed').count()
    stats['my_assets_count'] = Asset.objects.filter(assigned_to=user).count()

    # 2. IT Support Stats
    # 2. IT Support Stats
    if user.groups.filter(name='IT Support').exists() or user.is_superuser:
        # Card 1: My Open Tickets
        stats['tickets_open'] = Ticket.objects.filter(assigned_to=user).exclude(status='Closed').count()
        # stats['tickets_open'] kept name same for template compatibility, but logic is specialized now
        
        # Card 2: Pending Maintenance (My Asset/Infra Maint)
        from maintenance.models import AssetMaintenance, InfraMaintenance
        my_asset_maint = AssetMaintenance.objects.filter(technician=user, status__in=['Scheduled', 'In Progress']).count()
        my_infra_maint = InfraMaintenance.objects.filter(technician=user, status__in=['Scheduled', 'In Progress']).count()
        stats['pending_maintenance'] = my_asset_maint + my_infra_maint
        
        # Card 3: Resolved This Month (By Me)
        now = timezone.now()
        stats['tickets_resolved_month'] = Ticket.objects.filter(
            assigned_to=user,
            status__in=['Resolved', 'Closed'],
            updated_at__month=now.month,
            updated_at__year=now.year
        ).count()
        
        # High Priority list (Generic or Scoped? Sticking to generic for awareness, or scoped?)
        # User only asked for Cards. Let's scope High List too for consistency if requested later, but for now leave generic or scope it?
        # "tampilkan saja ticket ... untuk dirinya sendiri". Safe to scope list too.
        stats['tickets_high_list'] = Ticket.objects.filter(assigned_to=user, priority='High').exclude(status='Closed').order_by('-created_at')[:5]
        
        # Check if daily log exists for today
        today = timezone.localdate()
        stats['my_daily_log_done'] = DailyLog.objects.filter(executor=user, date=today).exists()
    
    # 3. Manager Stats
    if user.groups.filter(name='Administrator').exists() or user.is_superuser:
        now = timezone.now()
        stats['total_tickets_month'] = Ticket.objects.filter(created_at__month=now.month, created_at__year=now.year).count()
        # Mocking SLA Breach for now since logic might be complex
        stats['sla_breach_count'] = Ticket.objects.filter(due_date__lt=now, status__in=['Open', 'In Progress']).count()
        stats['total_assets'] = Asset.objects.count()
        
        # Contracts Expiring Soon (30 Days)
        # Contracts Expiring Soon (30 Days) OR Recently Expired (Last 30 Days)
        # Fix: Show items that expired recently so they don't disappear immediately
        stats['expiring_contracts'] = Contract.objects.filter(
            end_date__lte=timezone.localdate() + timedelta(days=30),
            end_date__gte=timezone.localdate() - timedelta(days=60) # Keep visible for 60 days after expiry
        ).exclude(status='CANCELLED').order_by('end_date')[:5]

        # Software Subscriptions Expiring Soon (30 Days) OR Recently Expired
        stats['expiring_software'] = Software.objects.filter(
            expiry_date__lte=timezone.localdate() + timedelta(days=30),
            expiry_date__gte=timezone.localdate() - timedelta(days=60) # Keep visible for 60 days after expiry
        ).exclude(license_type='PERPETUAL').order_by('expiry_date')[:5]

        # -----------------------------------------------------
        # NEW WIDGETS
        # -----------------------------------------------------
        
        # 1. Technician Workload (Top 5 busiest)
        # We look for users in 'IT Support' group
        stats['tech_workload'] = User.objects.filter(groups__name='IT Support').select_related('location').annotate(
            open_load=Count('tickets_assigned', filter=Q(tickets_assigned__status__in=['Open', 'In Progress']))
        ).order_by('-open_load')[:5]
        
        # 2. Upcoming Maintenance Journey (Next 7 Days)
        start_date = timezone.localdate()
        end_date = start_date + timedelta(days=7)
        
        asset_maint = AssetMaintenance.objects.filter(
            scheduled_date__range=[start_date, end_date], 
            status='Scheduled'
        ).select_related('asset')
        
        infra_maint = InfraMaintenance.objects.filter(
            scheduled_date__range=[start_date, end_date], 
            status='Scheduled'
        ).select_related('infrastructure')
        
        # Combine and Sort
        combined_maint = []
        for m in asset_maint:
            combined_maint.append({
                'title': m.title,
                'target': m.asset.name,
                'date': m.scheduled_date,
                'type': 'Asset',
                'technician': m.technician
            })
        for m in infra_maint:
            combined_maint.append({
                'title': m.title,
                'target': m.infrastructure.name,
                'date': m.scheduled_date,
                'type': 'Infrastructure',
                'technician': m.technician
            })
            
        # Sort by date
        combined_maint.sort(key=lambda x: x['date'])
        stats['upcoming_maintenance'] = combined_maint

    # --- Phase 42: Dynamic Greeting & Quotes ---
    # --- Phase 42: Dynamic Greeting & Quotes ---
    import random
    
    current_hour = datetime.now().hour
    if 5 <= current_hour < 11:
        stats['greeting'] = "Selamat Pagi ☕"
    elif 11 <= current_hour < 15:
        stats['greeting'] = "Selamat Siang ☀️"
    elif 15 <= current_hour < 18:
        stats['greeting'] = "Selamat Sore 🌇"
    else:
        stats['greeting'] = "Selamat Malam 🌙"
        
    quotes = [
        "Technology is best when it brings people together.",
        "First, solve the problem. Then, write the code.",
        "Stay productive, stay secure.",
        "Have you backed up your data today?",
        "It works on my machine!",
        "The best error message is the one that never shows up.",
        "Simplicity is the soul of efficiency.",
    ]
    stats['daily_quote'] = random.choice(quotes)
    # -------------------------------------------

    # 4. Activity Feed (Universal)
    activities = []
    
    # Recent Tickets
    for t in Ticket.objects.select_related('created_by').order_by('-created_at')[:5]:
        activities.append({
            'type': 'Ticket',
            'title': f"New Ticket #{t.id}",
            'description': t.title,
            'time': t.created_at,
            'user': t.created_by.username,
            'icon': 'fas fa-ticket-alt',
            'color': 'primary'
        })
        
    # Recent Assets
    for a in Asset.objects.order_by('-created_at')[:5]:
        activities.append({
            'type': 'Asset',
            'title': "Asset Registered",
            'description': f"{a.name} ({a.asset_code})",
            'time': a.created_at,
            'user': 'System', # Or created_by if available
            'icon': 'fas fa-box',
            'color': 'info'
        })
        
    # Recent Downtime
    # Need to import DowntimeEvent. Checking imports...
    # Assuming DowntimeEvent imported or I will add import.
    from network.models import DowntimeEvent
    for d in DowntimeEvent.objects.order_by('-start_time')[:5]:
        activities.append({
            'type': 'Downtime',
            'title': "Network Incident",
            'description': f"{d.title} ({d.get_impact_display()})",
            'time': d.start_time,
            'user': 'Monitoring',
            'icon': 'fas fa-bolt',
            'color': 'danger'
        })

    # --- Phase 53: Smart Work Queue ---
    work_queue = []
    
    # Define Scope
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
    is_it = user.groups.filter(name='IT Support').exists()
    
    from django.db.models import Q
    
    descendants = []
    if is_it and not is_admin:
        if hasattr(user, 'location') and user.location:
             descendants = user.location.get_descendants(include_self=True)
        else:
             descendants = []
             
    # 1. Fetch Tickets
    if is_admin:
        tickets_q = Ticket.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True)
        ).exclude(status='Closed')
    else:
        if descendants:
            descendant_ids = [loc.id for loc in descendants]
            loc_filter = Q(asset__location_id__in=descendant_ids) | Q(created_by__location_id__in=descendant_ids)
            
            tickets_q = Ticket.objects.filter(
                Q(assigned_to=user) | (Q(assigned_to__isnull=True) & loc_filter)
            ).exclude(status='Closed')
        else:
            tickets_q = Ticket.objects.filter(assigned_to=user).exclude(status='Closed')

    for t in tickets_q.select_related('created_by', 'asset', 'asset__location'):
        scope_label = 'My Task' if t.assigned_to == user else 'Unassigned'
        loc_name = "Unknown"
        if t.asset and t.asset.location:
             loc_name = t.asset.location.name
        elif t.created_by and hasattr(t.created_by, 'location') and t.created_by.location:
             loc_name = t.created_by.location.name
             
        # Status Color Map
        status_color = 'primary'
        if t.status == 'Open': status_color = 'danger'
        elif t.status == 'In_Progress': status_color = 'warning'
        elif t.status == 'Resolved': status_color = 'success'
        elif t.status == 'Pending_Vendor': status_color = 'info'
        
        work_queue.append({
            'type': 'Ticket',
            'id': t.ticket_code or t.id,
            'title': t.title,
            'priority': t.priority,
            'url': f"/tickets/{t.id}/",
            'deadline': t.due_date,
            'scope_label': scope_label,
            'location': loc_name,
            'created_at': t.created_at,
            'icon': 'fas fa-ticket-alt',
            'color': 'danger' if t.priority in ['High', 'Critical'] else 'primary',
            'status': t.get_status_display() if hasattr(t, 'get_status_display') else t.status,
            'status_color': status_color
        })

    # 2. Fetch Maintenance
    from maintenance.models import AssetMaintenance, InfraMaintenance
    from datetime import timedelta
    
    # 24-hour retention for completed tasks
    yesterday = timezone.localdate() - timedelta(days=1)
    
    # Filter Logic: Active OR (Completed AND Recent)
    active_or_recent_q = Q(status__in=['Scheduled', 'In Progress']) | Q(status='Completed', completed_date__gte=yesterday)

    if is_admin:
         maint_q = AssetMaintenance.objects.filter(
             Q(technician=user) | Q(technician__isnull=True)
         ).filter(active_or_recent_q).exclude(status='Cancelled')
    else:
         if descendants:
             descendant_ids = [loc.id for loc in descendants]
             maint_q = AssetMaintenance.objects.filter(
                 Q(technician=user) | (Q(technician__isnull=True) & Q(asset__location_id__in=descendant_ids))
             ).filter(active_or_recent_q).exclude(status='Cancelled')
         else:
             maint_q = AssetMaintenance.objects.filter(technician=user).filter(active_or_recent_q).exclude(status='Cancelled')
             
    for m in maint_q.select_related('asset', 'asset__location'):
        scope_label = 'My Task' if m.technician == user else 'Unassigned'
        
        # Convert date to datetime
        deadline_dt = None
        if m.scheduled_date:
            deadline_dt = datetime.combine(m.scheduled_date, datetime.min.time())

        status_color = 'info'
        if m.status == 'Scheduled': status_color = 'primary'
        elif m.status == 'In Progress': status_color = 'warning'
        elif m.status == 'Completed': status_color = 'success'

        work_queue.append({
            'type': 'Maintenance',
            'id': f"M-{m.id}",
            'title': m.title,
            'priority': 'Medium',
            'url': f"/maintenance/", 
            'deadline': deadline_dt,
            'scope_label': scope_label,
            'location': m.asset.location.name if m.asset and m.asset.location else "-",
            'created_at': m.scheduled_date, 
            'icon': 'fas fa-tools',
            'color': 'warning',
            'status': m.status,
            'status_color': status_color
        })

    # 3. Fetch Infra Maintenance
    if is_admin:
         infra_maint_q = InfraMaintenance.objects.filter(
             Q(technician=user) | Q(technician__isnull=True)
         ).filter(active_or_recent_q).exclude(status='Cancelled')
    else:
         if descendants:
             descendant_ids = [loc.id for loc in descendants]
             # Infra maintenance usually tied to infrastructure -> location
             # Infrastructure has 'location' field.
             infra_maint_q = InfraMaintenance.objects.filter(
                 Q(technician=user) | (Q(technician__isnull=True) & Q(infrastructure__location_id__in=descendant_ids))
             ).filter(active_or_recent_q).exclude(status='Cancelled')
         else:
             infra_maint_q = InfraMaintenance.objects.filter(technician=user).filter(active_or_recent_q).exclude(status='Cancelled')
             
    # Helper for date conversion
    from datetime import datetime
    
    for m in infra_maint_q.select_related('infrastructure', 'infrastructure__location'):
        scope_label = 'My Task' if m.technician == user else 'Unassigned'
        
        # Convert date to datetime for template compatibility (H:i filter support)
        deadline_dt = None
        if m.scheduled_date:
            deadline_dt = datetime.combine(m.scheduled_date, datetime.min.time())
            
        status_color = 'info'
        if m.status == 'Scheduled': status_color = 'primary'
        elif m.status == 'In Progress': status_color = 'warning'
        elif m.status == 'Completed': status_color = 'success'

        work_queue.append({
            'type': 'Infra Maint',
            'id': f"I-{m.id}",
            'title': m.title,
            'priority': 'Medium',
            'url': f"/maintenance/", 
            'deadline': deadline_dt,
            'scope_label': scope_label,
            'location': m.infrastructure.location.name if m.infrastructure and m.infrastructure.location else "-",
            'created_at': m.scheduled_date, 
            'icon': 'fas fa-server',
            'color': 'dark',
            'status': m.status,
            'status_color': status_color
        })
        
    def get_sort_weight(item):
        # User requested "Tanggal Terbaru Diatas" (Newest date on top).
        # We will sort by date descending.
        dt = item.get('deadline') or item.get('created_at')
        if not dt:
             return timezone.datetime.min
        # Return timestamp for simple comparison
        if hasattr(dt, 'timestamp'):
             return dt.timestamp()
        # If it's a date object
        from datetime import datetime
        return datetime.combine(dt, datetime.min.time()).timestamp()

    # Sort: Date Descending (Newest/Latest first)
    work_queue.sort(key=lambda x: get_sort_weight(x), reverse=True)
    
    stats['work_queue'] = work_queue

    # [RESTORED] Sort and Slice Activity Feed
    activities.sort(key=lambda x: x['time'], reverse=True)
    stats['activity_feed'] = activities[:10]

    # [NEW] Branch Health (Root Locations)
    if is_admin: 
        from assets.models import Location
        root_locs = Location.objects.filter(parent__isnull=True)
        branch_health = []
        
        for loc in root_locs:
            subtree = loc.get_descendants(include_self=True)
            subtree_ids = [l.id for l in subtree]
            
            assets_count = Asset.objects.filter(location_id__in=subtree_ids).count()
            tickets_open = Ticket.objects.filter(asset__location_id__in=subtree_ids).exclude(status='Closed').count()
            tickets_critical = Ticket.objects.filter(asset__location_id__in=subtree_ids, priority='Critical').exclude(status='Closed').count()
            
            # Maintenance Counts
            from maintenance.models import AssetMaintenance, InfraMaintenance
            asset_maint_count = AssetMaintenance.objects.filter(
                asset__location_id__in=subtree_ids, 
                status__in=['Scheduled', 'In Progress']
            ).count()
            
            infra_maint_count = InfraMaintenance.objects.filter(
                infrastructure__location_id__in=subtree_ids,
                status__in=['Scheduled', 'In Progress']
            ).count()

            # Simple Health Score
            score = 100 - (tickets_critical * 20) - (tickets_open * 2) - (infra_maint_count * 5)
            score = max(0, score)
            
            status = 'Healthy'
            color = 'success'
            if score < 60:
                status = 'Critical'
                color = 'danger'
            elif score < 85:
                status = 'Warning'
                color = 'warning'
                
            branch_health.append({
                'name': loc.name,
                'total_assets': assets_count,
                'open_tickets': tickets_open,
                'critical_tickets': tickets_critical,
                'asset_maint': asset_maint_count,
                'infra_maint': infra_maint_count,
                'health_score': score,
                'status': status,
                'color': color
            })
        stats['branch_health'] = branch_health

    return stats

@login_required
def admin_dashboard(request):
    context = get_dashboard_stats(request.user)
    return render(request, 'core/dashboard_admin.html', context)

@login_required
def it_dashboard(request):
    context = get_dashboard_stats(request.user)
    return render(request, 'core/dashboard_it.html', context)

@login_required
def staff_dashboard(request):
    context = get_dashboard_stats(request.user)
    return render(request, 'core/dashboard_staff.html', context)

# --- ASSET ANALYTICS APIs ---

@login_required
def chart_asset_distribution(request):
    """
    API for Asset Distribution by Purchase Year
    """
    data = Asset.objects.annotate(year=ExtractYear('purchase_date')).values('year').annotate(count=Count('id')).order_by('year')
    
    labels = [str(item['year']) if item['year'] else 'Unknown' for item in data]
    counts = [item['count'] for item in data]
    
    return JsonResponse({'labels': labels, 'data': counts})

@login_required
def chart_asset_maintenance_costs(request):
    """
    API for Top 10 Assets by Maintenance Cost
    """
    data = Asset.objects.annotate(
        total_cost=Sum('assetmaintenance__cost')
    ).exclude(total_cost__isnull=True).order_by('-total_cost')[:10]
    
    labels = [asset.name for asset in data]
    costs = [asset.total_cost for asset in data]
    
    return JsonResponse({'labels': labels, 'data': costs})

# --- TICKET ANALYTICS APIs ---

@login_required
def chart_ticket_categories(request):
    """
    API for Tickets by Category
    """
    data = Ticket.objects.values('topic__category').annotate(count=Count('id')).order_by('topic__category')
    # topic__category is a Choice field or string. 
    # If using TicketTopic model, it might be topic__name or topic__category depending on model.
    # Checking tickets models... Ticket -> topic (TicketTopic) -> category (CharField choice)
    
    labels = [item['topic__category'] for item in data]
    counts = [item['count'] for item in data]
    
    return JsonResponse({'labels': labels, 'data': counts})

@login_required
def chart_tickets_monthly(request):
    """
    API for Tickets Created in Last 6 Months
    """
    # Simply get counts by Month-Year
    # Using simple approach for sqlite/postgres compatibility
    # Just last 6 months
    
    # We can use truncation or extraction
    data = Ticket.objects.annotate(
        month=ExtractMonth('created_at'),
        year=ExtractYear('created_at')
    ).values('month', 'year').annotate(count=Count('id')).order_by('year', 'month')
    
    # Limit to last few? The query gets all. We can slice python side or filter date.
    # Let's filter date > 6 months ago
    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    data = data.filter(created_at__gte=six_months_ago)

    labels = [f"{item['year']}-{item['month']}" for item in data]
    counts = [item['count'] for item in data]

    return JsonResponse({'labels': labels, 'data': counts})

# --- MODULE STUBS ---



class InfrastructureView(TemplateView):
    template_name = 'core/under_construction.html'

class UserManagementView(TemplateView):
    template_name = 'core/under_construction.html'

class MaintenanceScheduleView(TemplateView):
    template_name = 'core/under_construction.html'

def home(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.groups.filter(name='Administrator').exists():
            return redirect('admin_dashboard')
        elif request.user.groups.filter(name='IT Support').exists():
            return redirect('it_dashboard')
        else:
            return redirect('staff_dashboard')
    return redirect('login')

from django.views import View
from django.db.models import Q
from knowledge.models import Article
from django.contrib.auth import get_user_model

class GlobalSearchView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        query = request.GET.get('q', '').strip()
        results = []
        
        if len(query) < 2:
            return JsonResponse({'results': []})

        # --- Scoping Logic ---
        # 1. Admin/Superuser/Manager -> Global Scope
        is_global = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager']).exists()
        
        # 2. Branch IT -> Local Scope (Descendants of their location)
        allowed_locations = []
        if not is_global and hasattr(user, 'location') and user.location:
             allowed_locations = user.location.get_descendants(include_self=True)
             
        # Helper filter
        def get_scoped_filter(model_type):
            if is_global:
                return Q() # No filter
            
            if not allowed_locations:
                # If no location assigned but not global, maybe show nothing or just assigned to them?
                # Let's default to "Assigned to Me" strictly if no location logic applies
                if model_type == 'Asset':
                     return Q(assigned_to=user)
                if model_type == 'Ticket':
                     return Q(assigned_to=user) | Q(created_by=user)
                return Q(pk__in=[]) # Fail safe
                
            # Location based filter
            loc_ids = [l.id for l in allowed_locations]
            if model_type == 'Asset':
                return Q(location_id__in=loc_ids)
            if model_type == 'Ticket':
                # Tickets in my location OR created by users in my location OR assigned to me
                return Q(asset__location_id__in=loc_ids) | Q(created_by__location_id__in=loc_ids) | Q(assigned_to=user)
            if model_type == 'NetworkNode':
                return Q(location_id__in=loc_ids)
            if model_type == 'User':
                return Q(location_id__in=loc_ids)
            if model_type == 'Maintenance':
                return Q(asset__location_id__in=loc_ids) | Q(technician=user)
            if model_type == 'InfraMaintenance':
                return Q(infrastructure__location_id__in=loc_ids) | Q(technician=user)
                
            return Q()

        # 1. Assets
        assets = Asset.objects.filter(
            (Q(name__icontains=query) | 
            Q(asset_code__icontains=query) |
            Q(serial_number__icontains=query)) &
            get_scoped_filter('Asset')
        )[:5]
        for asset in assets:
            results.append({
                'type': 'Asset',
                'text': f"{asset.name} ({asset.asset_code})",
                'detail': asset.location.name if asset.location else 'No Location',
                'url': f"/assets/{asset.id}/", 
                'icon': 'fas fa-laptop'
            })
            
        # 2. Tickets
        tickets = Ticket.objects.filter(
            (Q(title__icontains=query) |
            Q(ticket_code__icontains=query)) &
            get_scoped_filter('Ticket')
        )[:5]
        for ticket in tickets:
            results.append({
                'type': 'Ticket',
                'text': f"{ticket.ticket_code} {ticket.title}",
                'detail': ticket.get_status_display(),
                'url': f"/tickets/{ticket.id}/",
                'icon': 'fas fa-ticket-alt'
            })
            
        # 3. Tasks (Maintenance)
        from maintenance.models import AssetMaintenance, InfraMaintenance
        
        # Search Asset Maintenance
        asset_maint = AssetMaintenance.objects.filter(
            (Q(title__icontains=query) |
            Q(maintenance_code__icontains=query)) &
            get_scoped_filter('Maintenance')
        )[:3]
        for m in asset_maint:
            results.append({
                'type': 'Task',
                'text': f"{m.maintenance_code} - {m.title}",
                'detail': 'Asset Maintenance',
                'url': f"/maintenance/", 
                'icon': 'fas fa-tools'
            })

        # Search Infra Maintenance
        infra_maint = InfraMaintenance.objects.filter(
            (Q(title__icontains=query) |
            Q(maintenance_code__icontains=query)) &
            get_scoped_filter('InfraMaintenance')
        )[:3]
        for m in infra_maint:
            results.append({
                'type': 'Task',
                'text': f"{m.maintenance_code} - {m.title}",
                'detail': 'Infra Maintenance',
                'url': f"/maintenance/", 
                'icon': 'fas fa-server'
            })
            
        # 4. Users
        User = get_user_model()
        users = User.objects.filter(
            (Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)) &
            get_scoped_filter('User')
        )[:5]
        for u in users:
            results.append({
                'type': 'User',
                'text': u.get_full_name() or u.username,
                'detail': u.job_title or 'Staff',
                'url': f"/administration/users/", 
                'icon': 'fas fa-user'
            })
            
        # 5. Network Nodes
        nodes = NetworkNode.objects.filter(
            (Q(name__icontains=query) |
            Q(ip_address__icontains=query)) &
            get_scoped_filter('NetworkNode')
        )[:3]
        for node in nodes:
            results.append({
                'type': 'Node',
                'text': f"{node.name} ({node.ip_address})",
                'detail': node.location.name if node.location else '-',
                'url': f"/network/nodes/",
                'icon': 'fas fa-network-wired'
            })
            
        # 6. Knowledge Base (Usually Global, but can optionally restrict)
        # For now, let's keep it global as knowledge is shared.
        articles = Article.objects.filter(title__icontains=query)[:3]
        for article in articles:
            results.append({
                'type': 'Article',
                'text': article.title,
                'detail': 'Knowledge Base',
                'url': f"/knowledge/article/{article.id}/",
                'icon': 'fas fa-book'
            })

        return JsonResponse({'results': results})
