from django.urls import path
from . import views

urlpatterns = [
    # Daily Logs
    path('logs/', views.DailyLogListView.as_view(), name='dailylog_list'),
    path('logs/events-json/', views.DailyLogEventsJSON.as_view(), name='dailylog_events_json'),
    path('logs/create/', views.DailyLogCreateView.as_view(), name='dailylog_create'),
    path('logs/<int:pk>/', views.DailyLogDetailView.as_view(), name='dailylog_detail'),
    path('logs/<int:pk>/print/', views.DailyLogPrintView.as_view(), name='dailylog_print'),
    path('logs/<int:pk>/edit/', views.DailyLogUpdateView.as_view(), name='dailylog_update'),
    path('logs/bulk-approve/', views.DailyLogBulkApproveView.as_view(), name='dailylog_bulk_approve'),
    
    # Projects
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('projects/tasks/<int:pk>/complete/', views.CompleteProjectTaskView.as_view(), name='complete_project_task'),
    path('logs/<int:pk>/add-item/', views.DailyLogItemCreateView.as_view(), name='dailylog_item_create'),
    
    # Other Governance Modules
    path('fiscal-years/', views.FiscalDashboardView.as_view(), name='fiscal_year_list'),
    path('monthly-reports/', views.MonthlyReportListView.as_view(), name='monthly_report_list'),
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    
    # Disposal
    path('disposals/', views.DisposalListView.as_view(), name='disposal_list'),
]
