from django.urls import path
from . import views

urlpatterns = [
    path('', views.AssetListView.as_view(), name='asset_list'),
    path('create/', views.AssetCreateView.as_view(), name='asset_create'),
    path('<int:pk>/', views.AssetDetailView.as_view(), name='asset_detail'),
    path('<int:pk>/update/', views.AssetUpdateView.as_view(), name='asset_update'),
    path('<int:pk>/delete/', views.AssetDeleteView.as_view(), name='asset_delete'),
    path('storage/<int:pk>/delete/', views.AssetStorageDeleteView.as_view(), name='asset_storage_delete'),
    path('scanner/', views.AssetScannerView.as_view(), name='asset_scanner'),
    path('resolve-code/', views.AssetResolveCodeView.as_view(), name='asset_resolve_code'),
    
    path('<int:pk>/inspection/print/', views.AssetInspectionPrintView.as_view(), name='asset_inspection_print'),
    path('<int:asset_id>/document/add/', views.AssetDocumentUploadView.as_view(), name='asset_document_upload'),
    path('document/<int:pk>/delete/', views.AssetDocumentDeleteView.as_view(), name='asset_document_delete'),
    path('<int:pk>/print-label/', views.AssetLabelView.as_view(), name='asset_print_label'),
    path('print-labels/', views.BulkAssetLabelView.as_view(), name='asset_print_labels_bulk'),
    path('print-list-bulk/', views.BulkAssetPrintListView.as_view(), name='asset_print_list_bulk'),
    path('print/<str:token>/', views.AssetDetailPrintView.as_view(), name='asset_detail_print'),
    path('print-report/', views.AssetReportView.as_view(), name='asset_print_report'),
    path('<int:pk>/maintenance/add/', views.AssetMaintenanceCreateView.as_view(), name='asset_maintenance_add'),
    path('maintenance/<int:pk>/edit/', views.AssetMaintenanceUpdateView.as_view(), name='asset_maintenance_update'),
    path('maintenance/<int:pk>/delete/', views.AssetMaintenanceDeleteView.as_view(), name='asset_maintenance_delete'),
    
    path('<int:pk>/loan/add/', views.AssetLoanCreateView.as_view(), name='asset_loan_add'),
    path('loan/<int:pk>/edit/', views.AssetLoanUpdateView.as_view(), name='asset_loan_update'),
    path('loan/<int:pk>/delete/', views.AssetLoanDeleteView.as_view(), name='asset_loan_delete'),
    path('loan/<int:pk>/receipt/', views.AssetLoanReceiptView.as_view(), name='asset_loan_receipt'),
    
    path('<int:pk>/note/update/', views.AssetNoteUpdateView.as_view(), name='asset_note_update'),
    path('analytics/', views.AssetSmartAnalyticsView.as_view(), name='asset_analytics'),
    path('reports/financials/', views.AssetFinancialView.as_view(), name='asset_financials'),
    path('export/', views.AssetExportView.as_view(), name='asset_export'),
    path('<int:asset_id>/part-history/add/', views.PartHistoryCreateView.as_view(), name='part_history_add'),
    path('part-history/<int:pk>/delete/', views.PartHistoryDeleteView.as_view(), name='part_history_delete'),
    path('print-list/', views.AssetPrintListView.as_view(), name='asset_print_list'),

    # Software Asset Management
    path('software/', views.SoftwareListView.as_view(), name='software_list'),
    path('software/create/', views.SoftwareCreateView.as_view(), name='software_create'),
    path('software/<int:pk>/', views.SoftwareDetailView.as_view(), name='software_detail'),
    path('software/<int:pk>/update/', views.SoftwareUpdateView.as_view(), name='software_update'),
    path('software/<int:software_pk>/assign/', views.SoftwareAllocationCreateView.as_view(), name='software_allocation_add'),
    path('software/allocation/<int:pk>/delete/', views.SoftwareAllocationDeleteView.as_view(), name='software_allocation_delete'),

    # Cloud Hosting & Domain Management
    path('cloud/', views.CloudListView.as_view(), name='cloud_list'),
    path('cloud/create/', views.CloudCreateView.as_view(), name='cloud_create'),
    path('cloud/<int:pk>/update/', views.CloudUpdateView.as_view(), name='cloud_update'),

    path('cloud/<int:pk>/delete/', views.CloudDeleteView.as_view(), name='cloud_delete'),
    
    # Infrastructure
    path('infrastructure/', views.InfrastructureListView.as_view(), name='infra_list'),
    path('infrastructure/create/', views.InfrastructureCreateView.as_view(), name='infra_create'),
    path('infrastructure/<int:pk>/', views.InfrastructureDetailView.as_view(), name='infra_detail'),
    path('infrastructure/<int:pk>/link-asset/', views.InfrastructureLinkAssetView.as_view(), name='infra_link_asset'),
    path('infrastructure/<int:pk>/print-datasheet/', views.InfrastructurePrintDatasheetView.as_view(), name='infra_print_datasheet'),
    path('infrastructure/<int:infra_id>/part-history/add/', views.InfraPartHistoryCreateView.as_view(), name='infra_part_history_add'),
    path('infrastructure/part-history/<int:pk>/delete/', views.InfraPartHistoryDeleteView.as_view(), name='infra_part_history_delete'),
    path('infrastructure/<int:pk>/print-label/', views.InfrastructurePrintLabelView.as_view(), name='infra_print_label'),
    path('infrastructure/print-labels/', views.BulkInfraLabelView.as_view(), name='infra_print_labels_bulk'),
    path('infrastructure/<int:pk>/update/', views.InfrastructureUpdateView.as_view(), name='infra_update'),
    path('infrastructure/<int:pk>/delete/', views.InfrastructureDeleteView.as_view(), name='infra_delete'),

    # Unified Maintenance - Moved to maintenance app
    # path('maintenance/', views.MaintenanceDashboardView.as_view(), name='maintenance_dashboard'),
    path('maintenance/export/', views.MaintenanceExportView.as_view(), name='maintenance_export'),
    
    path('maintenance/asset/add/', views.AssetMaintenanceCreateView.as_view(), name='asset_maintenance_create'),
    path('maintenance/asset/<int:pk>/update/', views.AssetMaintenanceUpdateView.as_view(), name='asset_maintenance_update'),
    path('maintenance/asset/<int:pk>/delete/', views.AssetMaintenanceDeleteView.as_view(), name='asset_maintenance_delete'),

    path('maintenance/infra/add/', views.InfraMaintenanceCreateView.as_view(), name='infra_maintenance_create'),
    path('maintenance/infra/<int:pk>/update/', views.InfraMaintenanceUpdateView.as_view(), name='infra_maintenance_update'),
    path('maintenance/infra/<int:pk>/delete/', views.InfraMaintenanceDeleteView.as_view(), name='infra_maintenance_delete'),

    # Contracts
    path('contracts/', views.ContractListView.as_view(), name='contract_list'),
    path('contracts/add/', views.ContractCreateView.as_view(), name='contract_create'),
    path('contracts/<int:pk>/', views.ContractDetailView.as_view(), name='contract_detail'),
    path('contracts/<int:pk>/update/', views.ContractUpdateView.as_view(), name='contract_update'),
    path('contracts/<int:pk>/delete/', views.ContractDeleteView.as_view(), name='contract_delete'),
    path('contracts/<int:pk>/renew/', views.ContractRenewView.as_view(), name='contract_renew'),

    # Location Command Center
    path('locations/', views.LocationTreeView.as_view(), name='location_tree'),
    path('locations/<int:pk>/details/', views.LocationDetailAjaxView.as_view(), name='location_detail_ajax'),
    path('locations/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/update/', views.LocationUpdateView.as_view(), name='location_update'),
    path('locations/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='location_delete'),
    # Vendor Management
    path('vendors/', views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/add/', views.VendorCreateView.as_view(), name='vendor_create'),
    path('vendors/<int:pk>/update/', views.VendorUpdateView.as_view(), name='vendor_update'),
    path('vendors/<int:pk>/delete/', views.VendorDeleteView.as_view(), name='vendor_delete'),
    # Category Management
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('api/capex/', views.CapexDataAPI.as_view(), name='api_capex_data'),
    path('api/maintenance-pivot/', views.MaintenancePivotAPI.as_view(), name='api_maintenance_pivot'),
]