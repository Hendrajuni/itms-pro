from django.urls import path
from . import views

urlpatterns = [
    path('', views.MaintenanceDashboardView.as_view(), name='maintenance_dashboard'),
    
    # Schedule (PM) URLs
    path('schedules/', views.MaintenanceScheduleListView.as_view(), name='maintenance_schedule_list'),
    path('schedules/create/', views.MaintenanceScheduleCreateView.as_view(), name='maintenance_schedule_create'),
    path('schedules/<int:pk>/update/', views.MaintenanceScheduleUpdateView.as_view(), name='maintenance_schedule_update'),
    path('schedules/<int:pk>/delete/', views.MaintenanceScheduleDeleteView.as_view(), name='maintenance_schedule_delete'),
    path('schedules/<int:pk>/generate/', views.maintenance_schedule_generate, name='maintenance_schedule_generate'),
]
