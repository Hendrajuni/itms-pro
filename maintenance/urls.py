from django.urls import path
from . import views

urlpatterns = [
    path('', views.MaintenanceDashboardView.as_view(), name='maintenance_dashboard'),
    
    # AJAX Endpoints
    path('api/toggle-checklist/', views.toggle_checklist_item, name='toggle_checklist_item'),
    path('api/quick-status/', views.quick_status_update, name='quick_status_update'),
    path('api/task-detail/<str:task_type>/<int:pk>/', views.task_detail_api, name='task_detail_api'),
    path('api/add-subtask/', views.add_subtask, name='add_subtask'),
    
    # Schedule (PM) URLs
    path('schedules/', views.MaintenanceScheduleListView.as_view(), name='maintenance_schedule_list'),
    path('schedules/create/', views.MaintenanceScheduleCreateView.as_view(), name='maintenance_schedule_create'),
    path('schedules/<int:pk>/update/', views.MaintenanceScheduleUpdateView.as_view(), name='maintenance_schedule_update'),
    path('schedules/<int:pk>/delete/', views.MaintenanceScheduleDeleteView.as_view(), name='maintenance_schedule_delete'),
    path('schedules/<int:pk>/generate/', views.maintenance_schedule_generate, name='maintenance_schedule_generate'),
]
