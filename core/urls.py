from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('accounts/login/', views.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Dashboards
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/it/', views.it_dashboard, name='it_dashboard'),
    path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'),

    # APIs (Assets)
    path('api/chart/asset-distribution/', views.chart_asset_distribution, name='chart_asset_distribution'),
    path('api/chart/maintenance-costs/', views.chart_asset_maintenance_costs, name='chart_asset_maintenance_costs'),

    # APIs (Tickets)
    path('api/chart/ticket-categories/', views.chart_ticket_categories, name='chart_ticket_categories'),
    path('api/chart/tickets-monthly/', views.chart_tickets_monthly, name='chart_tickets_monthly'),
    
    # Module Stubs



    path('maintenance/', views.MaintenanceScheduleView.as_view(), name='maintenance_list'),
    
    # Global Search
    path('global-search/', views.GlobalSearchView.as_view(), name='global_search'),
    path('', views.home, name='home'),
]
