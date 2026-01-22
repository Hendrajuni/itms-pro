from django.urls import path
from . import views

urlpatterns = [
    path('', views.MaintenanceDashboardView.as_view(), name='maintenance_dashboard'),
]
