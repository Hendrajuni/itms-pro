from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/export/', views.UserExportView.as_view(), name='user_export'),
    path('users/print/', views.UserPrintView.as_view(), name='user_print'),
    path('org-chart/', views.OrgChartView.as_view(), name='org_chart'),
    
    # Department Management
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department_delete'),

    # Regional Heads
    path('departments/regional/create/', views.RegionalHeadCreateView.as_view(), name='regional_head_create'),
    path('departments/regional/<int:pk>/delete/', views.RegionalHeadDeleteView.as_view(), name='regional_head_delete'),

    path('users/toggle/<int:pk>/', views.UserToggleStatusView.as_view(), name='user_toggle_status'),
    path('users/reset-password/<int:pk>/', views.AdminPasswordResetView.as_view(), name='admin_password_reset'),
    
    # User Profile
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/password/', views.UserChangePasswordView.as_view(), name='user_password_change'),
    
    # Audit Log
    path('audit-log/', views.AuditLogListView.as_view(), name='audit_log_list'),
    
    # Site Settings
    path('settings/', views.SiteSettingsView.as_view(), name='site_settings'),
    path('settings/backup/', views.DatabaseBackupView.as_view(), name='database_backup'),
]
