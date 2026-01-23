from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/export/', views.UserExportView.as_view(), name='user_export'),
    path('users/print/', views.UserPrintView.as_view(), name='user_print'),
    path('users/toggle/<int:pk>/', views.UserToggleStatusView.as_view(), name='user_toggle_status'),
    path('users/reset-password/<int:pk>/', views.AdminPasswordResetView.as_view(), name='admin_password_reset'),
    
    # User Profile
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/password/', views.UserChangePasswordView.as_view(), name='user_password_change'),
    
    # Audit Log
    path('audit-log/', views.AuditLogListView.as_view(), name='audit_log_list'),
    
    # Site Settings
    path('settings/', views.SiteSettingsView.as_view(), name='site_settings'),
]
