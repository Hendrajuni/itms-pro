from django.urls import path
from .views import NotificationSettingsView, TestNotificationView

app_name = 'integrations'

urlpatterns = [
    path('settings/', NotificationSettingsView.as_view(), name='settings'),
    path('test-notification/', TestNotificationView.as_view(), name='test_notification'),
]
