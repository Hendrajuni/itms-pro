from django.urls import path
from . import views

urlpatterns = [
    path('downtimes/', views.DowntimeDashboardView.as_view(), name='downtime_list'),
    path('downtimes/report/', views.ReportDowntimeView.as_view(), name='report_downtime'),
    path('downtimes/<int:pk>/resolve/', views.ResolveDowntimeView.as_view(), name='resolve_downtime'),
    
    path('nodes/', views.NetworkNodeListView.as_view(), name='network_node_list'),
    path('nodes/add/', views.NetworkNodeCreateView.as_view(), name='network_node_create'),
    path('nodes/<int:pk>/edit/', views.NetworkNodeUpdateView.as_view(), name='network_node_update'),
    path('nodes/<int:pk>/delete/', views.NetworkNodeDeleteView.as_view(), name='network_node_delete'),
    path('nodes/ping/<int:pk>/', views.PingNodeView.as_view(), name='ping_node'),
    
    path('ips/', views.SubnetListView.as_view(), name='ip_list'), # Keeping for legacy if needed, or redirect
    path('ips/<int:pk>/edit/', views.IPAddressUpdateView.as_view(), name='ip_edit'),
    path('ips/<int:pk>/assign/', views.AssignIpView.as_view(), name='assign_ip'),
    path('isp-lines/', views.ISPLineListView.as_view(), name='isp_line_list'),
    
    # Main Dashboard (Redesigned)
    path('subnets/', views.SubnetTreeDashboardView.as_view(), name='subnet_list'),
    path('subnets/ajax-list/<int:pk>/', views.SubnetListAjaxView.as_view(), name='subnet_list_ajax'),
    
    path('subnets/<int:pk>/', views.SubnetDetailView.as_view(), name='subnet_detail'),
    path('subnets/<int:subnet_id>/add-ip/', views.IPAddressCreateView.as_view(), name='ip_add'),
    path('subnets/add/', views.SubnetCreateView.as_view(), name='subnet_create'),
    path('subnets/<int:pk>/print/', views.SubnetPrintView.as_view(), name='subnet_print'),
]
