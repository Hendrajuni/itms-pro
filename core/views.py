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
from assets.models import Asset, Contract
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
    stats = {}
    
    # 1. Staff Stats
    # Always relevant or if user is staff
    stats['my_tickets_count'] = Ticket.objects.filter(created_by=user).exclude(status='Closed').count()
    stats['my_assets_count'] = Asset.objects.filter(assigned_to=user).count()

    # 2. IT Support Stats
    if user.groups.filter(name='IT Support').exists() or user.is_superuser:
        stats['tickets_open'] = Ticket.objects.exclude(status='Closed').count()
        stats['tickets_high'] = Ticket.objects.filter(priority='High').exclude(status='Closed').count()
        # Add list for table
        stats['tickets_high_list'] = Ticket.objects.filter(priority='High').exclude(status='Closed').order_by('-created_at')[:5]
        
        stats['servers_down'] = NetworkNode.objects.filter(status='Offline').count()
        
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
        stats['expiring_contracts'] = Contract.objects.filter(
            end_date__lte=timezone.localdate() + timedelta(days=30),
            end_date__gte=timezone.localdate()
        ).exclude(status='CANCELLED')[:5]

    # --- Phase 42: Dynamic Greeting & Quotes ---
    import datetime
    import random
    
    current_hour = datetime.datetime.now().hour
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

    # Sort and Slice
    activities.sort(key=lambda x: x['time'], reverse=True)
    stats['activity_feed'] = activities[:10]

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
        query = request.GET.get('q', '').strip()
        results = []
        
        if len(query) < 2:
            return JsonResponse({'results': []})
            
        # 1. Assets
        assets = Asset.objects.filter(
            Q(name__icontains=query) | 
            Q(asset_code__icontains=query) |
            Q(serial_number__icontains=query)
        )[:5]
        for asset in assets:
            results.append({
                'type': 'Asset',
                'text': f"{asset.name} ({asset.asset_code})",
                'url': f"/assets/{asset.id}/", # Assuming asset detail URL pattern
                'icon': 'fas fa-laptop'
            })
            
        # 2. Tickets
        tickets = Ticket.objects.filter(
            Q(title__icontains=query) |
            Q(ticket_code__icontains=query)
        )[:5]
        for ticket in tickets:
            results.append({
                'type': 'Ticket',
                'text': f"{ticket.ticket_code} {ticket.title}",
                'url': f"/tickets/{ticket.id}/",
                'icon': 'fas fa-ticket-alt'
            })
            
        # 3. Network Nodes
        nodes = NetworkNode.objects.filter(
            Q(name__icontains=query) |
            Q(ip_address__icontains=query)
        )[:5]
        for node in nodes:
            results.append({
                'type': 'Node',
                'text': f"{node.name} ({node.ip_address})",
                'url': f"/network/nodes/", # No detail view yet, go to list
                'icon': 'fas fa-server'
            })
            
        # 4. Knowledge Base
        articles = Article.objects.filter(title__icontains=query)[:5]
        for article in articles:
            results.append({
                'type': 'Article',
                'text': article.title,
                'url': f"/knowledge/article/{article.id}/",
                'icon': 'fas fa-book'
            })
            
        # 5. Users
        User = get_user_model()
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )[:5]
        for user in users:
            # Only show if user is admin/staff? Everyone can see users.
            results.append({
                'type': 'User',
                'text': user.get_full_name() or user.username,
                'url': f"#", # No public profile view other than admin
                'icon': 'fas fa-user'
            })
            
        return JsonResponse({'results': results})
