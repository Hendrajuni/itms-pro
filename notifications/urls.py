from django.urls import path
from . import views

urlpatterns = [
    path('mark-read/<int:pk>/', views.MarkNotificationReadView.as_view(), name='notification_mark_read'),
    path('mark-all-read/', views.MarkAllReadView.as_view(), name='notification_mark_all_read'),
]
