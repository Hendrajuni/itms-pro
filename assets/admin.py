from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from django.utils.html import mark_safe
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.contrib import messages
from django.shortcuts import redirect
from .models import Department, Location, Vendor, Category, Asset, AssetSpecification, AssetIPAddress, NetworkInterface, Infrastructure, AssetLoan, Software, SoftwareAllocation, CloudAsset, Contract, AssetStorage, AuditItem, PartHistory

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')
    search_fields = ('name',)

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'contact_person')
    search_fields = ('name', 'email')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type')
    list_filter = ('type',)
    search_fields = ('name',)

class AssetSpecificationInline(admin.StackedInline):
    model = AssetSpecification
    can_delete = False

class NetworkInterfaceInline(admin.TabularInline):
    model = NetworkInterface
    extra = 1

class AssetIPAddressInline(admin.TabularInline):
    # Deprecated but kept for viewing legacy data if any
    model = AssetIPAddress
    extra = 0

class SoftwareAllocationInline(admin.TabularInline):
    model = SoftwareAllocation
    extra = 0

class AssetStorageInline(admin.TabularInline):
    model = AssetStorage
    extra = 0
    fields = ('device_type', 'brand', 'capacity', 'serial_number', 'purchase_date')

class AuditItemInline(admin.TabularInline):
    model = AuditItem
    extra = 0
    readonly_fields = ('session_id', 'status', 'scanned_at', 'notes')
    can_delete = True

class PartHistoryInline(admin.TabularInline):
    model = PartHistory
    extra = 0
    can_delete = True




@admin.register(Asset)
class AssetAdmin(ImportExportModelAdmin):
    list_display = ('asset_code', 'name', 'category', 'status', 'assigned_to', 'purchase_date')
    list_filter = ('status', 'category', 'location', 'department', 'infrastructure')
    search_fields = ('asset_code', 'name', 'serial_number')
    readonly_fields = ('asset_code', 'qr_code_preview')
    exclude = ('qr_code_image',)
    exclude = ('qr_code_image',)
    exclude = ('qr_code_image',)
    exclude = ('qr_code_image',)
    inlines = [AssetSpecificationInline, AssetStorageInline, NetworkInterfaceInline, SoftwareAllocationInline, AuditItemInline, PartHistoryInline]




    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return mark_safe(f'<img src="{obj.qr_code_image.url}" width="150" height="150" style="border:1px solid #ccc;"/>')
        return "No QR Code"
    qr_code_preview.short_description = "QR Code Preview"

    qr_code_preview.short_description = "QR Code Preview"

@admin.register(Software)
class SoftwareAdmin(ImportExportModelAdmin):
    list_display = ('name', 'vendor', 'license_type', 'seats_used', 'seats_total', 'expiry_date')
    list_filter = ('license_type', 'vendor')
    search_fields = ('name', 'license_key')
    inlines = [SoftwareAllocationInline]

@admin.register(Infrastructure)
class InfrastructureAdmin(admin.ModelAdmin):
    list_display = ('infra_id', 'name', 'location', 'type', 'condition', 'next_maintenance_date')
    search_fields = ('infra_id', 'name')
    list_filter = ('type', 'location')
    readonly_fields = ('infra_id',)
    # Removed qr_code_preview as field doesn't exist in current model

@admin.register(CloudAsset)
class CloudAssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'service_type', 'expiry_date', 'status')
    list_filter = ('service_type', 'provider', 'status')
    search_fields = ('name', 'provider', 'ip_address')
    readonly_fields = ('days_until_expiry',)

@admin.register(AssetLoan)
class AssetLoanAdmin(admin.ModelAdmin):
    list_display = ('loan_id', 'asset', 'employee', 'loan_date', 'return_date')
    list_filter = ('loan_date',)
    search_fields = ('loan_id', 'asset__asset_code', 'employee__username')
    readonly_fields = ('loan_id',)

@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('title', 'contract_type', 'vendor', 'end_date', 'status')
    list_filter = ('contract_type', 'status', 'vendor')
    search_fields = ('title', 'notes')
    date_hierarchy = 'end_date'
    readonly_fields = ('status',)

