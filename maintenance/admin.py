from django.contrib import admin
from .models import AssetMaintenance, InfraMaintenance

@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display = ('maintenance_code', 'title', 'asset', 'scheduled_date', 'status', 'cost')
    list_filter = ('status', 'maintenance_type', 'scheduled_date')
    search_fields = ('maintenance_code', 'title', 'asset__name')
    readonly_fields = ('maintenance_code',)

@admin.register(InfraMaintenance)
class InfraMaintenanceAdmin(admin.ModelAdmin):
    list_display = ('maintenance_code', 'title', 'infrastructure', 'scheduled_date', 'status', 'cost')
    list_filter = ('status', 'maintenance_type', 'scheduled_date')
    search_fields = ('maintenance_code', 'title', 'infrastructure__name')
    readonly_fields = ('maintenance_code',)
