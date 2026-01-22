from django.urls import path
from . import views

urlpatterns = [
    path('downtimes/', views.DowntimeDashboardView.as_view(), name='downtime_list'),
    path('downtimes/report/', views.ReportDowntimeView.as_view(), name='report_downtime'),
    path('downtimes/<int:pk>/resolve/', views.ResolveDowntimeView.as_view(), name='resolve_downtime'),
    
    path('nodes/', views.NetworkNodeListView.as_view(), name='network_node_list'),
    path('nodes/ping/<int:pk>/', views.PingNodeView.as_view(), name='ping_node'),
    
    path('ips/', views.IPAddressListView.as_view(), name='ip_list'),
    path('ips/<int:pk>/assign/', views.AssignIpView.as_view(), name='assign_ip'),
    path('isp-lines/', views.ISPLineListView.as_view(), name='isp_line_list'),
    path('subnets/', views.SubnetListView.as_view(), name='subnet_list'),
    path('subnets/<int:pk>/print/', views.SubnetPrintView.as_view(), name='subnet_print'),
]
