from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import ISPLine, NetworkNode
from .utils import check_ping

@admin.register(ISPLine)
class ISPLineAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'capacity_mbps', 'status', 'monthly_cost')
    list_filter = ('status', 'provider')
    search_fields = ('name', 'cid_number')

@admin.register(NetworkNode)
class NetworkNodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'ip_address', 'status_colored', 'last_checked', 'location')
    list_filter = ('type', 'status', 'location')
    search_fields = ('name', 'ip_address', 'notes')
    autocomplete_fields = ['asset', 'location']
    actions = ['scan_selected_nodes']

    def status_colored(self, obj):
        color = 'green' if obj.status == 'Online' else 'red'
        if obj.status == 'Maintenance':
            color = 'orange'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status
        )
    status_colored.short_description = 'Status'

    def scan_selected_nodes(self, request, queryset):
        success_count = 0
        fail_count = 0
        
        for node in queryset:
            if not node.ip_address:
                continue
                
            is_online = check_ping(node.ip_address)
            
            if is_online:
                node.status = 'Online'
                success_count += 1
            else:
                node.status = 'Offline'
                fail_count += 1
            
            node.last_checked = timezone.now()
            node.save(update_fields=['status', 'last_checked'])
            
        self.message_user(request, f"Scan Completed. Online: {success_count}, Offline: {fail_count}")
    scan_selected_nodes.short_description = "Run Ping Check on selected nodes"

from .models import Subnet, IPAddress

class IPAddressInline(admin.TabularInline):
    model = IPAddress
    extra = 1
    fields = ('address', 'status', 'node', 'asset', 'description')

@admin.register(Subnet)
class SubnetAdmin(admin.ModelAdmin):
    list_display = ('name', 'cidr', 'location', 'gateway', 'vlan_id')
    list_filter = ('location',)
    search_fields = ('name', 'cidr')
    inlines = [IPAddressInline]

@admin.register(IPAddress)
class IPAddressAdmin(admin.ModelAdmin):
    list_display = ('address', 'subnet', 'get_location', 'status', 'node', 'asset', 'get_assigned_user', 'updated_at')
    list_filter = ('subnet__location', 'subnet', 'status')
    search_fields = ('address', 'node__name', 'asset__name', 'description', 'asset__assigned_to__username')
    autocomplete_fields = ['node', 'subnet', 'asset']

    def get_assigned_user(self, obj):
        if obj.asset and obj.asset.assigned_to:
            return obj.asset.assigned_to.username
        return '-'
    get_assigned_user.short_description = 'User'

    def get_location(self, obj):
        if obj.subnet and obj.subnet.location:
            return obj.subnet.location.name
        return '-'
    get_location.short_description = 'Location'
    get_location.admin_order_field = 'subnet__location'

from .models import DowntimeEvent

@admin.register(DowntimeEvent)
class DowntimeEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'node', 'asset', 'start_time', 'duration', 'is_resolved', 'technician')
    list_filter = ('is_resolved', 'root_cause', 'technician')
    search_fields = ('title', 'resolution')
    autocomplete_fields = ['node', 'asset', 'infrastructure']
    readonly_fields = ('duration',)
