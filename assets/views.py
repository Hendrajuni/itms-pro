from django.shortcuts import render, get_object_or_404
from django import forms
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Sum
from django.db import IntegrityError
from django.db.models import Q, Count, Sum, F, ExpressionWrapper, fields, ProtectedError
from django.db.models.functions import ExtractYear, ExtractMonth
from django.utils import timezone
from datetime import timedelta
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse, HttpResponse
from django.core.files.base import ContentFile
import base64
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from .models import Asset, AssetSpecification, NetworkInterface, AssetLoan, Software, SoftwareAllocation, CloudAsset, Infrastructure, InfrastructureType, Contract, Location, Department, Category, AssetStorage, Vendor, PartHistory, AssetDocument
from governance.models import DailyLog, Project
from maintenance.models import AssetMaintenance, InfraMaintenance
from .forms import AssetForm, AssetNoteForm, NetworkInterfaceFormSet, AssetStorageFormSet, SoftwareAllocationFormSet, AssetLoanForm, AssetMaintenanceForm, InfraMaintenanceForm, SoftwareForm, SoftwareAllocationForm, CloudAssetForm, InfrastructureForm, ContractForm, LocationForm, PartHistoryForm, VendorForm, AssetDocumentForm
from django.db.models import Sum, Q, Count, F
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

class AssetListView(LoginRequiredMixin, ListView):
    model = Asset
    template_name = 'assets/asset_list.html'
    context_object_name = 'assets'
    ordering = ['-created_at']
    paginate_by = 20

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page')
        if per_page and per_page.isdigit():
            return int(per_page)
        return self.paginate_by

    def get_queryset(self):
        queryset = super().get_queryset().select_related('category', 'assigned_to', 'department', 'location', 'location__parent')
        
        # Scoped Access: IT Support sees only their hierarchy
        user = self.request.user
        is_manager = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        is_it_support = user.groups.filter(name='IT Support').exists()

        if is_it_support and not is_manager:
            if hasattr(user, 'location') and user.location:
                descendants = user.location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                queryset = queryset.filter(location_id__in=descendant_ids)
            else:
                queryset = queryset.none()  # Unassigned IT sees nothing
        elif not is_manager and not is_it_support:
            # Standard User: See ONLY assigned assets
            queryset = queryset.filter(assigned_to=user)
        
        # View Mode Logic
        view_mode = self.request.GET.get('mode', 'operational')
        
        if view_mode == 'disposed':
            queryset = queryset.filter(status='DISPOSED')
        else:
            # Default: operational, financial, lifecycle -> Exclude DISPOSED
            queryset = queryset.exclude(status='DISPOSED')

        # Filter: Status (New)
        status_filter = self.request.GET.get('status')
        if status_filter:
            # If specifically asking for LOST/RETIRED/DISPOSED, we must include them 
            # even if excluded above. But above logic uses 'mode'.
            # If mode='disposed', we already see disposed.
            # If mode='operational' (default), we excluded disposed.
            # If user filters status='LOST', we should show it.
            # So, re-filter/include based on specific status?
            # Actually, the exclusion of 'DISPOSED' happens if mode != 'disposed'.
            # If user selects status='DISPOSED' via filter but mode is 'operational', it might conflict.
            # Let's trust the filter overrides or works within valid set.
            # For LOST/RETIRED, they are not 'DISPOSED' so they are in queryset.
            queryset = queryset.filter(status=status_filter)

        # Filter: Location (Recursive: Include children)
        loc = self.request.GET.get('loc')
        if loc:
            try:
                selected_loc = Location.objects.get(id=loc)
                descendants = selected_loc.get_descendants(include_self=True)
                descendant_ids = [l.id for l in descendants]
                queryset = queryset.filter(location_id__in=descendant_ids)
            except (ValueError, Location.DoesNotExist):
                pass
            
        # Filter: Department
        dept = self.request.GET.get('dept')
        if dept:
            queryset = queryset.filter(department_id=dept)

        # Filter: Category (Sidebar)
        cat = self.request.GET.get('category')
        if cat:
            queryset = queryset.filter(category_id=cat)

        # Search Logic
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | 
                Q(asset_code__icontains=q) |
                Q(serial_number__icontains=q) |
                Q(brand__icontains=q) |
                Q(model__icontains=q) |
                Q(location__name__icontains=q) |
                Q(assigned_to__username__icontains=q) |
                Q(assigned_to__first_name__icontains=q)
            )

        # Sorting Logic
        sort_by = self.request.GET.get('sort', '-created_at')
        groupby = self.request.GET.get('groupby')
        direction = self.request.GET.get('order', 'desc')
        
        # Override sort if grouping is active
        if groupby == 'location':
            # Group by Location Name
            queryset = queryset.order_by('location__name', 'name')
            return queryset
        
        # Mapping frontend sort keys to model fields
        sort_mapping = {
            'name': 'name',
            'code': 'asset_code',
            'category': 'category__name',
            'status': 'status',
            'purchase_date': 'purchase_date',
            'price': 'purchase_price',
            'created': 'created_at'
        }
        
        db_field = sort_mapping.get(sort_by, '-created_at')
        
        if direction == 'desc' and not db_field.startswith('-'):
            db_field = f'-{db_field}'
        elif direction == 'asc' and db_field.startswith('-'):
            db_field = db_field[1:] # Remove minus
            
        return queryset.order_by(db_field)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Pass view mode to template
        context['view_mode'] = self.request.GET.get('mode', 'operational')
        
        is_manager = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        is_it_support = user.groups.filter(name='IT Support').exists()

        context['is_it_support'] = is_it_support
        
        # Determine Scope for Filters & Counts
        descendants = []
        descendant_ids = []
        is_scoped = False
        
        if is_it_support and not is_manager:
             is_scoped = True
             if hasattr(user, 'location') and user.location:
                 descendants = user.location.get_descendants(include_self=True)
                 descendant_ids = [loc.id for loc in descendants]
                 context['locations_flat'] = descendants
                 context['use_optgroup'] = False
             else:
                 context['locations_flat'] = []
                 context['use_optgroup'] = False
        else:
             # Admin: Group by Root (Province)
             context['location_roots'] = Location.objects.filter(parent__isnull=True).prefetch_related('children')
             context['use_optgroup'] = True

        context['departments'] = Department.objects.all()
        
        # Summary Stats (Admin/Manager/IT)
        if is_manager or is_it_support:
            # Calculate sum of current filtered queryset (self.object_list)
            # Efficient aggregation
            summary = self.object_list.aggregate(
                total_value=Sum('purchase_price'),
                total_count=Count('id')
            )
            context['summary_total_value'] = summary['total_value'] or 0
            context['summary_total_count'] = summary['total_count'] or 0
            
        context['groupby'] = self.request.GET.get('groupby')
        
        # Category Counts for Sidebar
        # Only show categories that have at least one asset (accessible to user)
        if is_scoped:
            if descendant_ids:
                context['category_counts'] = Category.objects.annotate(
                    asset_count=Count('assets', filter=Q(assets__location_id__in=descendant_ids))
                ).filter(asset_count__gt=0).order_by('name')
            else:
                context['category_counts'] = []
        else:
            context['category_counts'] = Category.objects.annotate(
                asset_count=Count('assets')
            ).filter(asset_count__gt=0).order_by('name')
        
        # View Mode Logic
        view_mode = self.request.GET.get('mode', 'operational')
        context['view_mode'] = view_mode
        context['current_sort'] = self.request.GET.get('sort', 'created')
        context['current_order'] = self.request.GET.get('order', 'desc')
        context['current_category'] = self.request.GET.get('category')
        
        # Helper for Dropdown Labels
        context['current_loc'] = self.request.GET.get('loc')
        if context['current_loc']:
            try:
                context['selected_location'] = Location.objects.get(id=context['current_loc'])
            except Location.DoesNotExist: pass

        context['current_dept'] = self.request.GET.get('dept')
        if context['current_dept']:
            try:
                context['selected_department'] = Department.objects.get(id=context['current_dept'])
            except Department.DoesNotExist: pass
        
        if context['current_category']:
            try:
                context['selected_category'] = Category.objects.get(id=context['current_category'])
            except Category.DoesNotExist:
                context['selected_category'] = None
        
        return context

class AssetExportView(AssetListView):
    def get(self, request, *args, **kwargs):
        # reuse filters from AssetListView
        queryset = self.get_queryset()
        view_mode = request.GET.get('mode', 'operational')
        
        wb = openpyxl.Workbook()
        ws = wb.active
        
        # Styling
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4e73df", end_color="4e73df", fill_type="solid")
        
        # Define Columns based on Mode
        if view_mode == 'financial':
            filename = f"ITMS_Financial_Report_{timezone.now().date()}.xlsx"
            headers = ['Asset Code', 'Name', 'Category', 'Purchase Date', 'Purchase Price', 'Depreciation', 'Current Value', 'Total Maint. Cost']
            ws.title = "Financial Report"
        elif view_mode == 'lifecycle':
            filename = f"ITMS_Lifecycle_Report_{timezone.now().date()}.xlsx"
            headers = ['Asset Code', 'Name', 'Purchase Date', 'Age', 'Warranty Ends', 'Status', 'User']
            ws.title = "Lifecycle Report"
        else: # operational
            filename = f"ITMS_Inventory_Report_{timezone.now().date()}.xlsx"
            headers = ['Asset Code', 'Name', 'Specs (Brand/Model)', 'Location', 'User', 'Status', 'Serial Number']
            ws.title = "Operational Report"
            
        # Write Header
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            
        # Write Data
        for row_num, asset in enumerate(queryset, 2):
            if view_mode == 'financial':
                ws.cell(row=row_num, column=1, value=asset.asset_code)
                ws.cell(row=row_num, column=2, value=asset.name)
                ws.cell(row=row_num, column=3, value=str(asset.category) if asset.category else '-')
                ws.cell(row=row_num, column=4, value=asset.purchase_date)
                ws.cell(row=row_num, column=5, value=asset.purchase_price)
                
                # depreciation logic (simple calc for export)
                cur_val = asset.get_current_value()
                dep_val = (asset.purchase_price or 0) - cur_val
                
                ws.cell(row=row_num, column=6, value=dep_val).number_format = '#,##0'
                ws.cell(row=row_num, column=7, value=cur_val).number_format = '#,##0'
                ws.cell(row=row_num, column=8, value=asset.get_total_maintenance_cost()).number_format = '#,##0'
                
            elif view_mode == 'lifecycle':
                ws.cell(row=row_num, column=1, value=asset.asset_code)
                ws.cell(row=row_num, column=2, value=asset.name)
                ws.cell(row=row_num, column=3, value=asset.purchase_date)
                ws.cell(row=row_num, column=4, value=asset.age_usage)
                ws.cell(row=row_num, column=5, value=asset.warranty_end)
                ws.cell(row=row_num, column=6, value=asset.get_status_display())
                ws.cell(row=row_num, column=7, value=str(asset.assigned_to) if asset.assigned_to else 'Unassigned')
                
            else: # operational
                ws.cell(row=row_num, column=1, value=asset.asset_code)
                ws.cell(row=row_num, column=2, value=asset.name)
                specs = f"{asset.brand or ''} {asset.model or ''}".strip()
                ws.cell(row=row_num, column=3, value=specs)
                ws.cell(row=row_num, column=4, value=str(asset.location) if asset.location else '-')
                ws.cell(row=row_num, column=5, value=str(asset.assigned_to) if asset.assigned_to else 'Unassigned')
                ws.cell(row=row_num, column=6, value=asset.get_status_display())
                ws.cell(row=row_num, column=7, value=asset.serial_number)
                
        # Auto-adjust column width
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter # Get the column name
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column].width = adjusted_width
            
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response
        return context

class AssetReportView(LoginRequiredMixin, ListView):
    model = Asset
    template_name = 'assets/print_report.html'
    context_object_name = 'assets'
    ordering = ['category', 'name']

    def get_queryset(self):
        # Re-use search logic for report
        queryset = super().get_queryset().select_related('category', 'assigned_to', 'location')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | 
                Q(asset_code__icontains=q) |
                Q(serial_number__icontains=q) |
                Q(brand__icontains=q) |
                Q(model__icontains=q) |
                Q(location__name__icontains=q) |
                Q(assigned_to__username__icontains=q) |
                Q(assigned_to__first_name__icontains=q)
            )
        return queryset

class AssetLabelView(LoginRequiredMixin, DetailView):
    model = Asset
    template_name = 'assets/print_label.html'
    context_object_name = 'asset'

class AssetScannerView(LoginRequiredMixin, TemplateView):
    template_name = 'assets/asset_scanner.html'

class BulkAssetLabelView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        asset_ids = request.POST.getlist('selected_assets')
        if not asset_ids:
            messages.warning(request, "No assets selected.")
            return redirect('asset_list')
            
        assets = Asset.objects.filter(id__in=asset_ids)
        
        # Split into chunks of 24 (3x8) for A4
        chunks = [assets[i:i + 24] for i in range(0, len(assets), 24)]
        
        context = {
            'chunks': chunks,
            'today': timezone.now().date(),
        }
        
        return render(request, 'assets/asset_print_labels_bulk.html', context)

class BulkAssetPrintListView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        asset_ids = request.POST.getlist('selected_assets')
        mode = request.POST.get('mode')
        if not mode:
            mode = 'operational'
        
        if not asset_ids:
            messages.warning(request, "No assets selected.")
            return redirect('asset_list')
            
        # Get Assets ordered by category then name
        assets = Asset.objects.filter(id__in=asset_ids).select_related(
            'category', 'location', 'department', 'assigned_to', 'vendor'
        ).order_by('category__name', 'name')
        
        context = {
            'assets': assets,
            'today': timezone.now().date(),
            'print_date': timezone.now(),
            'report_title': 'Asset Selection Report',
            'filter_display': f'Self-Selected ({len(assets)} Assets)',
            'mode': mode
        }
        
        return render(request, 'assets/asset_print_list.html', context)

from django.db import transaction

class AssetCreateView(LoginRequiredMixin, CreateView):
    model = Asset
    form_class = AssetForm
    template_name = 'assets/asset_form.html'
    success_url = reverse_lazy('asset_list')
    
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['network_interfaces'] = NetworkInterfaceFormSet(self.request.POST, form_kwargs={'user': self.request.user})
            data['storage_formset'] = AssetStorageFormSet(self.request.POST)
            data['software_formset'] = SoftwareAllocationFormSet(self.request.POST)
        else:
            data['network_interfaces'] = NetworkInterfaceFormSet(form_kwargs={'user': self.request.user})
            data['storage_formset'] = AssetStorageFormSet()
            data['software_formset'] = SoftwareAllocationFormSet()
        return data

    def form_valid(self, form):
        # License Check: Limit Assets for Essential Edition
        from core.license import check_asset_limit
        if not check_asset_limit():
            messages.error(self.request, "License Restriction: Essential Edition is limited to 100 Assets. Please upgrade to Enterprise.")
            return self.render_to_response(self.get_context_data(form=form))

        context = self.get_context_data()
        network_interfaces = context['network_interfaces']
        storage_formset = context['storage_formset']
        software_formset = context['software_formset']
        
        if network_interfaces.is_valid() and storage_formset.is_valid() and software_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                
                network_interfaces.instance = self.object
                network_interfaces.save()
                
                storage_formset.instance = self.object
                storage_formset.save()
                
                software_formset.instance = self.object
                software_formset.save()
                
            messages.success(self.request, "Asset created successfully!")
            return redirect(self.success_url)
        else:
            # If formsets are invalid, render response with context (which contains errors)
            # form is valid here, but we treat it as invalid overall
            messages.error(self.request, "Please check the form for errors.")
            return self.render_to_response(self.get_context_data(form=form))

class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = Asset
    form_class = AssetForm
    template_name = 'assets/asset_form.html'
    success_url = reverse_lazy('asset_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
             data['network_interfaces'] = NetworkInterfaceFormSet(self.request.POST, instance=self.object, form_kwargs={'user': self.request.user})
             data['storage_formset'] = AssetStorageFormSet(self.request.POST, instance=self.object)
             data['software_formset'] = SoftwareAllocationFormSet(self.request.POST, instance=self.object)
        else:
             data['network_interfaces'] = NetworkInterfaceFormSet(instance=self.object, form_kwargs={'user': self.request.user})
             data['storage_formset'] = AssetStorageFormSet(instance=self.object)
             data['software_formset'] = SoftwareAllocationFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        network_interfaces = context['network_interfaces']
        storage_formset = context['storage_formset']
        software_formset = context['software_formset']
        
        if network_interfaces.is_valid() and storage_formset.is_valid() and software_formset.is_valid():
             with transaction.atomic():
                 self.object = form.save()
                 network_interfaces.instance = self.object
                 network_interfaces.save()
                 storage_formset.instance = self.object
                 storage_formset.save()
                 software_formset.instance = self.object
                 software_formset.save()
             messages.success(self.request, "Asset updated successfully!")
             return redirect(self.success_url)
        else:
             messages.error(self.request, "Please check the form for errors.")
             return self.render_to_response(self.get_context_data(form=form))

class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = Asset
    template_name = 'assets/asset_confirm_delete.html' 
    success_url = reverse_lazy('asset_list')

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError as e:
            # Provide a friendly error message listing the dependent objects
            protected_objects = list(e.protected_objects)
            msg = f"Cannot delete this asset because it is referenced by {len(protected_objects)} records: "
            msg += ", ".join([str(obj) for obj in protected_objects[:3]])
            if len(protected_objects) > 3:
                msg += "..."
            messages.error(request, msg)
            return redirect('asset_detail', pk=self.get_object().pk)
        except IntegrityError as e:
            msg = "Cannot delete this asset because it is referenced by other records (Database Constraint)."
            if 'assets_assetstorage' in str(e):
                msg = "Cannot delete: This asset is linked to 'Asset Storage' records (likely a hidden or legacy dependency). Please check database directly or contact admin."
            messages.error(request, msg)
            return redirect('asset_detail', pk=self.get_object().pk)

class AssetDetailView(LoginRequiredMixin, DetailView):
    model = Asset
    template_name = 'assets/asset_detail.html'
    context_object_name = 'asset'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        loans = list(self.object.loans.all().order_by('-loan_date')) if hasattr(self.object, 'loans') else []
        for i, loan in enumerate(loans):
            loan.previous_user = loans[i+1].employee if i + 1 < len(loans) else None
        context['history'] = loans
        
        maintenance_logs = self.object.maintenances.all().order_by('-scheduled_date') if hasattr(self.object, 'maintenances') else []
        # Note: 'maintenances' related name might default to assetmaintenance_set if not defined explicitly.
        # But our previous edits used related_name='maintenances' (or we assumed so).
        # Let's handle safe lookup.
        
        context['maintenance_logs'] = maintenance_logs
        
        # New: Part History & Cost Calculations
        part_history = self.object.part_history.all().order_by('-action_date')
        context['part_history'] = part_history
        
        # Calculate Total Costs
        total_parts_cost = part_history.aggregate(total=Sum('cost'))['total'] or 0
        total_maintenance_cost = self.object.maintenances.aggregate(total=Sum('cost'))['total'] or 0
        purchase_price = self.object.purchase_price or 0
        
        context['total_parts_cost'] = total_parts_cost
        context['total_maintenance_cost'] = total_maintenance_cost
        context['total_spend'] = purchase_price + total_parts_cost + total_maintenance_cost
        
        # Pass specification safely
        context['spec'] = self.object.safe_specification
        
        # Pass network interfaces
        context['interfaces'] = self.object.network_interfaces.all()
        
        # Storages
        context['storages'] = self.object.storages.all()
        
        # Permissions
        user = self.request.user
        context['is_admin'] = user.is_superuser or user.groups.filter(name='Admin').exists()
        context['is_it'] = user.groups.filter(name='IT').exists()
        
        return context

class AssetDetailPrintView(DetailView):
    model = Asset
    template_name = 'assets/asset_print_detail.html'
    context_object_name = 'asset'

    def get_object(self, queryset=None):
        from django.core import signing
        from django.http import Http404
        token = self.kwargs.get('token')
        try:
            pk = signing.loads(token)
            return Asset.objects.get(pk=pk)
        except (signing.BadSignature, Asset.DoesNotExist):
            raise Http404("Invalid or expired print link.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Populate context similar to detail view for report
        context['history'] = self.object.loans.all().order_by('-loan_date') if hasattr(self.object, 'loans') else []
        
        # New: Part History & Cost Calculations
        part_history = self.object.part_history.all().order_by('-action_date')
        context['part_history'] = part_history
        
        # Calculate Total Costs
        total_parts_cost = part_history.aggregate(total=Sum('cost'))['total'] or 0
        total_maintenance_cost = self.object.maintenances.aggregate(total=Sum('cost'))['total'] or 0
        purchase_price = self.object.purchase_price or 0
        
        context['total_parts_cost'] = total_parts_cost
        context['total_maintenance_cost'] = total_maintenance_cost
        context['total_spend'] = purchase_price + total_parts_cost + total_maintenance_cost
        
        # Maintenance logs
        maintenance_logs = self.object.maintenances.all().order_by('-scheduled_date') if hasattr(self.object, 'maintenances') else []
        context['maintenance_logs'] = maintenance_logs
        
        # Specification
        context['spec'] = self.object.safe_specification
        
        # Network interfaces
        context['interfaces'] = self.object.network_interfaces.all()
        context['storages'] = self.object.storages.all()
        
        return context

class AssetMaintenanceCreateView(LoginRequiredMixin, CreateView):
    model = AssetMaintenance
    form_class = AssetMaintenanceForm
    template_name = 'maintenance/maintenance_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if 'pk' in self.kwargs:
            # Context-aware: Pre-select asset and hide field
            asset = get_object_or_404(Asset, pk=self.kwargs['pk'])
            form.fields['asset'].initial = asset
            form.fields['asset'].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        if 'pk' in self.kwargs:
            asset = get_object_or_404(Asset, pk=self.kwargs['pk'])
            form.instance.asset = asset
        return super().form_valid(form)

    def get_success_url(self):
        if 'pk' in self.kwargs:
            return reverse_lazy('asset_detail', kwargs={'pk': self.kwargs['pk']})
        return reverse_lazy('maintenance_dashboard')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'pk' in self.kwargs:
            context['asset'] = get_object_or_404(Asset, pk=self.kwargs['pk'])
        context['action_title'] = "Add Maintenance Log"
        return context

class AssetMaintenanceUpdateView(LoginRequiredMixin, UpdateView):
    model = AssetMaintenance
    form_class = AssetMaintenanceForm
    template_name = 'maintenance/maintenance_form.html'
    success_url = reverse_lazy('maintenance_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.object.asset
        context['action_title'] = "Edit Maintenance Log"
        return context

class AssetMaintenanceDeleteView(LoginRequiredMixin, DeleteView):
    model = AssetMaintenance
    success_url = reverse_lazy('maintenance_dashboard')
    template_name = 'assets/confirm_delete.html'

class AssetLoanCreateView(LoginRequiredMixin, CreateView):
    model = AssetLoan
    form_class = AssetLoanForm
    template_name = 'assets/asset_assign_form.html'

    def form_valid(self, form):
        asset = get_object_or_404(Asset, pk=self.kwargs['pk'])
        form.instance.asset = asset
        
        # Handle Signature
        signature_data = self.request.POST.get('signature_data')
        if signature_data:
            format, imgstr = signature_data.split(';base64,') 
            ext = format.split('/')[-1] 
            data = ContentFile(base64.b64decode(imgstr), name=f'signature_{asset.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}.{ext}')
            form.instance.signature_image = data
            form.instance.is_digital_sign = True
            
        return super().form_valid(form)

    def get_success_url(self):
        # Redirect to receipt after assignment? Or back to detail?
        # User might want to print immediately. 
        # For now, let's go to detail, but maybe we can show a message or redirect to receipt.
        # Let's stick to detail page as per standard flow, user can click print there.
        return reverse_lazy('asset_detail', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = get_object_or_404(Asset, pk=self.kwargs['pk'])
        context['action_title'] = "Assign Asset"
        return context

class AssetLoanReceiptView(LoginRequiredMixin, DetailView):
    model = AssetLoan
    template_name = 'assets/asset_loan_receipt.html'
    context_object_name = 'loan'

class AssetNoteUpdateView(LoginRequiredMixin, UpdateView):
    model = Asset
    form_class = AssetNoteForm
    template_name = 'assets/asset_action_form.html'

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_title'] = "Update Notes"
        return context

class AssetMaintenanceUpdateView(LoginRequiredMixin, UpdateView):
    model = AssetMaintenance
    form_class = AssetMaintenanceForm
    template_name = 'assets/asset_action_form.html'

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.object.asset.pk})

    def form_valid(self, form):
        if form.instance.status == 'Completed' and not form.instance.completed_date:
            form.instance.completed_date = timezone.now().date()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.object.asset
        context['action_title'] = "Edit Maintenance Log"
        return context

class AssetMaintenanceDeleteView(LoginRequiredMixin, DeleteView):
    model = AssetMaintenance
    template_name = 'assets/asset_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.object.asset.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.object.asset
        context['title'] = "Delete Maintenance Log"
        return context

class AssetLoanUpdateView(LoginRequiredMixin, UpdateView):
    model = AssetLoan
    form_class = AssetLoanForm
    template_name = 'assets/asset_assign_form.html'

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.object.asset.pk})
        
    def form_valid(self, form):
        # Handle Signature Update if provided
        signature_data = self.request.POST.get('signature_data')
        if signature_data:
            format, imgstr = signature_data.split(';base64,') 
            ext = format.split('/')[-1] 
            data = ContentFile(base64.b64decode(imgstr), name=f'signature_{self.object.asset.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}.{ext}')
            form.instance.signature_image = data
            form.instance.is_digital_sign = True
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.object.asset
        context['action_title'] = "Edit Assignment"
        return context

class AssetLoanDeleteView(LoginRequiredMixin, DeleteView):
    model = AssetLoan
    template_name = 'assets/asset_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.object.asset.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.object.asset
        context['title'] = "Delete Assignment"
        return context

class AssetStorageDeleteView(LoginRequiredMixin, DeleteView):
    model = AssetStorage
    template_name = 'assets/asset_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('asset_detail', kwargs={'pk': self.object.asset.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = self.object.asset
        context['title'] = "Delete Storage Device"
        return context

# Enterprise Only
from django.contrib.auth.mixins import UserPassesTestMixin
from core.license import is_enterprise

class AssetSmartAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'assets/smart_analytics.html'

    def test_func(self):
        # Allow any authenticated user, but we'll scope data later
        return self.request.user.is_authenticated

    def handle_no_permission(self):
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(self.request, "You don't have permission to view Analytics.")
        return redirect('dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 1. Location Tree & Scope
        context['location_roots'] = Location.objects.filter(parent=None)
        selected_loc_id = self.request.GET.get('loc')
        selected_location = None
        
        assets = Asset.objects.all()
        infrastructures = Infrastructure.objects.all()

        if selected_loc_id:
            try:
                selected_location = Location.objects.get(pk=selected_loc_id)
                context['selected_location'] = selected_location
                
                # Expand tree logic
                current = selected_location
                expanded = []
                while current:
                    expanded.append(current.id)
                    current = getattr(current, 'parent', None)
                context['expanded_location_ids'] = expanded
                
                # Fetch descendants
                descendants = selected_location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                assets = assets.filter(location_id__in=descendant_ids)
                infrastructures = infrastructures.filter(location_id__in=descendant_ids)
                
            except Location.DoesNotExist:
                pass
        
        # Base Data
        total_assets = assets.count()
        total_value = assets.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
        
        # --- TAB 1: OVERVIEW & PROCUREMENT ---
        context['total_assets'] = total_assets
        context['total_value'] = total_value
        
        # Category Composition
        cat_data = assets.values('category__name').annotate(count=Count('id')).order_by('-count')
        context['chart_category_labels'] = json.dumps([item['category__name'] for item in cat_data])
        context['chart_category_data'] = json.dumps([item['count'] for item in cat_data])
        
        # Recent Procurements (Last 10)
        recent_purchases = assets.filter(purchase_date__isnull=False).select_related('assigned_to', 'department', 'category').order_by('-purchase_date')[:10]
        context['recent_purchases'] = recent_purchases
        
        # Procurement Trend (CAPEX Last 6 Months)
        from collections import defaultdict
        import datetime
        from django.utils import timezone
        
        capex_monthly = defaultdict(float)
        six_months_ago = timezone.now().date() - datetime.timedelta(days=180)
        recent_assets = assets.filter(purchase_date__gte=six_months_ago, purchase_price__isnull=False)
        
        for a in recent_assets:
            month_label = a.purchase_date.strftime("%b %Y")
            capex_monthly[month_label] += float(a.purchase_price)
            
        sorted_capex_months = sorted(capex_monthly.keys(), key=lambda d: datetime.datetime.strptime(d, "%b %Y"))
        context['capex_labels'] = json.dumps(sorted_capex_months)
        context['capex_data'] = json.dumps([capex_monthly[m] for m in sorted_capex_months])
        context['total_recent_capex'] = sum(capex_monthly.values())

        # --- TAB 2: MAINTENANCE & OPEX ---
        # OPEX Logic
        opex_monthly = defaultdict(float)
        
        asset_maints = AssetMaintenance.objects.filter(asset__in=assets, status='Completed')
        for m in asset_maints:
            if m.completed_date:
                month_label = m.completed_date.strftime("%b %Y")
                opex_monthly[month_label] += float(m.cost or 0)
                
        infra_maints = InfraMaintenance.objects.filter(infrastructure__in=infrastructures, status='Completed')
        for m in infra_maints:
            if m.completed_date:
                month_label = m.completed_date.strftime("%b %Y")
                opex_monthly[month_label] += float(m.cost or 0)
                
        sorted_opex_months = sorted(opex_monthly.keys(), key=lambda d: datetime.datetime.strptime(d, "%b %Y"))
        sorted_opex_months = sorted_opex_months[-6:] if len(sorted_opex_months) > 6 else sorted_opex_months
        
        context['opex_labels'] = json.dumps(sorted_opex_months)
        context['opex_data'] = json.dumps([opex_monthly[m] for m in sorted_opex_months])
        context['total_opex'] = sum(opex_monthly.values())
        context['assets_broken'] = assets.filter(status='BROKEN').count()
        
        # Money Pits Check (Cost > 50% Price)
        money_pits = []
        asset_list = assets.prefetch_related('maintenances')
        for a in asset_list:
            maint_cost = sum(m.cost for m in a.maintenances.all()) if a.maintenances.exists() else 0
            purchase = a.purchase_price or 1
            if purchase > 1:
                ratio = (float(maint_cost) / float(purchase)) * 100
                if ratio > 50:
                    a.total_maint_cost = maint_cost
                    a.maintenance_ratio = ratio
                    money_pits.append(a)
        context['money_pit_assets'] = money_pits
        context['money_pit_count'] = len(money_pits)

        # --- TAB 3: LIFECYCLE & CONTRACTS ---
        today = timezone.now().date()
        eol_candidates = []
        for a in asset_list:
            if a.purchase_date:
                age_days = (today - a.purchase_date).days
                if age_days > (365 * 4):
                    eol_candidates.append(a)
        context['eol_candidates_count'] = len(eol_candidates)
        
        # Pending Disposals (Mock or fetch from disposal model if it exists, here we use disposed status)
        context['pending_disposals_count'] = assets.filter(status='DISPOSED').count()
        
        # Expiring Contracts (Next 90 Days)
        context['expiring_contracts'] = Contract.objects.filter(end_date__lte=today + datetime.timedelta(days=90), end_date__gte=today)
        context['expiring_contracts_count'] = context['expiring_contracts'].count()

        return context

class VendorListView(LoginRequiredMixin, ListView):
    model = Vendor
    template_name = 'assets/vendor_list.html'
    context_object_name = 'vendors'
    ordering = ['name']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(contact_person__icontains=q) |
                Q(email__icontains=q)
            )
        return queryset

class VendorCreateView(LoginRequiredMixin, CreateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'assets/vendor_form.html'
    success_url = reverse_lazy('vendor_list')

    def form_valid(self, form):
        messages.success(self.request, "Vendor created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_title'] = "Add New Vendor"
        return context

class VendorUpdateView(LoginRequiredMixin, UpdateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'assets/vendor_form.html'
    success_url = reverse_lazy('vendor_list')

    def form_valid(self, form):
        messages.success(self.request, "Vendor updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_title'] = "Edit Vendor"
        return context

class VendorDeleteView(LoginRequiredMixin, DeleteView):
    model = Vendor
    template_name = 'assets/asset_confirm_delete.html'
    success_url = reverse_lazy('vendor_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Vendor"
        context['message'] = f"Are you sure you want to delete vendor '{self.object.name}'? All related assets/contracts will need to be updated."
        return context
        
        # --- 1. Location Scope Logic (Tree Sidebar) ---
        # Get Root Locations for Sidebar
        location_roots = Location.objects.filter(parent__isnull=True).prefetch_related('children').order_by('name')
        
        # Filter Roots based on User Role
        is_manager = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        if not is_manager and hasattr(user, 'location') and user.location:
             # If restricted IT Support, only show their branch root
             my_root = user.location.get_root()
             location_roots = location_roots.filter(id=my_root.id)
             
        context['location_roots'] = location_roots
        
        # Determine Current Active Location Filter
        selected_location_id = self.request.GET.get('loc')
        selected_location = None
        filter_q = Q() # Default: All Assets
        
        if selected_location_id:
            try:
                selected_location = Location.objects.get(pk=selected_location_id)
                # Filter Logic: Include Descendants
                descendants = selected_location.get_descendants(include_self=True)
                subtree_ids = [d.id for d in descendants]
                filter_q = Q(location__in=descendants)
            except Location.DoesNotExist:
                pass
        elif not is_manager and hasattr(user, 'location') and user.location:
            # Default to user's location if not specified and restricted
            selected_location = user.location
            descendants = selected_location.get_descendants(include_self=True)
            filter_q = Q(location__in=descendants)
            subtree_ids = [d.id for d in descendants]
        else:
            subtree_ids = None

        context['selected_location'] = selected_location
        
        # Determine nodes to expand (Selected location + all ancestors)
        expanded_ids = []
        if selected_location:
            # Using MPTT's get_ancestors
            ancestors = selected_location.get_ancestors(include_self=True)
            expanded_ids = [loc.id for loc in ancestors]
        context['expanded_location_ids'] = expanded_ids
        base_assets = Asset.objects.filter(filter_q)
        financial_assets = base_assets.exclude(status='DISPOSED').filter(purchase_price__isnull=False, purchase_date__isnull=False)
        maintenance_logs = AssetMaintenance.objects.filter(asset__in=base_assets)
        
        # --- TAB 1: OVERVIEW (KPIs & Health) ---
        context['total_assets'] = base_assets.count()
        context['total_value'] = base_assets.aggregate(total=Sum('purchase_price'))['total'] or 0
        context['assets_broken'] = base_assets.filter(status='BROKEN').count()
        context['assets_disposed'] = base_assets.filter(status='DISPOSED').count()
        
        # Composition Chart (Category)
        cat_data = base_assets.values('category__name').annotate(count=Count('id')).order_by('-count')
        context['chart_category_labels'] = json.dumps([item['category__name'] for item in cat_data])
        context['chart_category_data'] = json.dumps([item['count'] for item in cat_data])

        # --- TAB 2: FINANCIALS (Depreciation & Budget) ---
        # Depreciation Logic (Top 50 Value)
        depreciation_list = []
        today = timezone.now().date()
        useful_life_days = 4 * 365
        
        # Predictive 1: 3-Year Capex Budget Forecast
        # Logic: Find assets reaching EOL (Purchase Date + 4 Years) in 2026, 2027, 2028
        current_year = today.year
        forecast_years = [current_year + 1, current_year + 2, current_year + 3]
        budget_forecast = {year: 0 for year in forecast_years}
        budget_forecast_counts = {year: 0 for year in forecast_years}
        
        # Predictive 2: Repair vs Replace (Money Pits)
        # Logic: Total Maintenance > 50% Purchase Price
        money_pit_assets = []
        
        for asset in financial_assets: 
            # Depreciation Calc
            age_days = (today - asset.purchase_date).days
            if age_days >= useful_life_days:
                current_value = 0
            else:
                depreciation = float(asset.purchase_price) * (age_days / useful_life_days)
                current_value = float(asset.purchase_price) - depreciation
            
            asset.cached_current_value = max(int(current_value), 0)
            depreciation_list.append(asset)
            
            # --- New: Budget Forecast Logic ---
            if asset.purchase_date:
                eol_date = asset.purchase_date + timedelta(days=useful_life_days)
                eol_year = eol_date.year
                if eol_year in forecast_years:
                    budget_forecast[eol_year] += (asset.purchase_price or 0)
                    budget_forecast_counts[eol_year] += 1
                
            # --- New: Repair vs Replace Logic ---
            if asset.purchase_price and asset.purchase_price > 0:
                # We need to calculate total maintenance. 
                # Optimization: We already fetched maintenance_logs for all base_assets.
                # Let's filter in memory (might be slow for huge DBs but fine for now) or use annotation.
                # For safety/speed, let's just use the method if efficient or sum from pre-fetched logs.
                # Ideally, we should have annotated `total_maintenance_cost` in the queryset.
                # Let's use a quick list comp filter on pre-fetched `maintenance_logs`
                asset_maint_logs = [m for m in maintenance_logs if m.asset_id == asset.id]
                total_maint = sum(m.cost or 0 for m in asset_maint_logs)
                
                cost_ratio = (total_maint / asset.purchase_price) * 100
                if cost_ratio > 50:
                    asset.maintenance_ratio = cost_ratio
                    asset.total_maint_cost = total_maint
                    money_pit_assets.append(asset)
            
        depreciation_list.sort(key=lambda x: x.cached_current_value, reverse=True)
        context['financial_top_assets'] = depreciation_list[:20]
        context['financial_total_depreciated_value'] = sum([a.cached_current_value for a in depreciation_list])
        
        # Sort Money Pits
        money_pit_assets.sort(key=lambda x: x.maintenance_ratio, reverse=True)
        context['money_pit_assets'] = money_pit_assets[:10]

        # Pass Forecast Data
        context['forecast_labels'] = json.dumps([str(y) for y in forecast_years])
        context['forecast_data'] = json.dumps([float(budget_forecast[y]) for y in forecast_years])
        context['forecast_counts'] = budget_forecast_counts
        
        # Forward-Looking: Contract Renewals
        context['expiring_contracts'] = Contract.objects.filter(
            replaced_by__isnull=True,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=90)
        ).order_by('end_date')

        # Replacement Forecast (Exceeds Useful Life in next 1 year)
        # Actually, let's show assets OLDER than 4 years (End of Life)
        eol_threshold = today - timedelta(days=useful_life_days)
        context['eol_candidates_count'] = financial_assets.filter(purchase_date__lt=eol_threshold).count()
        context['eol_candidates_value'] = financial_assets.filter(purchase_date__lt=eol_threshold).aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
        
        # --- TAB 3: OPTIMIZATION (Stock & Distribution) ---
        # Active vs Idle: Idle = 'In Stock'
        active_count = base_assets.exclude(status__in=['In Stock', 'BROKEN', 'DISPOSED']).count()
        idle_count = base_assets.filter(status='In Stock').count()
        
        context['stock_active'] = active_count
        context['stock_idle'] = idle_count
        context['utilization_rate'] = int((active_count / context['total_assets'] * 100)) if context['total_assets'] > 0 else 0
        
        
        # --- TAB 3 (Continued): DISPOSAL PIPELINE ---
        from governance.models import DisposalRequest
        
        # Filter disposals by location scope
        # We need assets belonging to the scope
        disposal_qs = DisposalRequest.objects.filter(status='Pending')
        if subtree_ids:
            disposal_qs = disposal_qs.filter(asset__location_id__in=subtree_ids)
            
        context['disposal_pending_count'] = disposal_qs.count()
        context['disposal_pending_value'] = disposal_qs.aggregate(Sum('asset__purchase_price'))['asset__purchase_price__sum'] or 0
        context['disposal_recent_list'] = disposal_qs.select_related('asset', 'requested_by').order_by('-request_date')[:5]

        # Regional Distribution (Bar Chart) - Only relevant if showing multiple locs
        # Group by immediate children of selected location (or roots if None)
        if selected_location:
             sub_locs = selected_location.get_children()
        else:
             sub_locs = Location.objects.filter(parent__isnull=True)
             
        regional_labels = []
        regional_data_count = []
        regional_data_value = []
        
        for loc in sub_locs:
            # Custom get_descendants returns a list, so we can't use values_list
            desc_nodes = loc.get_descendants(include_self=True)
            desc_ids = [n.id for n in desc_nodes]
            cnt = Asset.objects.filter(location_id__in=desc_ids).count()
            val = Asset.objects.filter(location_id__in=desc_ids).aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
            
            regional_labels.append(loc.name)
            regional_data_count.append(cnt)
            regional_data_value.append(float(val))
            
        context['chart_region_labels'] = json.dumps(regional_labels)
        context['chart_region_count'] = json.dumps(regional_data_count)
        context['chart_region_value'] = json.dumps(regional_data_value)
        
        return context

class AssetFinancialView(LoginRequiredMixin, TemplateView):
    template_name = 'assets/asset_financials.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Depreciation Calculation (Straight Line - 4 Years)
        # We'll do this in Python for flexibility with the "Top 50" requirement
        assets = Asset.objects.exclude(status='DISPOSED').filter(purchase_price__isnull=False, purchase_date__isnull=False)
        depreciation_list = []
        today = timezone.now().date()
        useful_life_days = 4 * 365
        
        for asset in assets:
            age_days = (today - asset.purchase_date).days
            # Value = Price - (Price * (Age/Life))
            if age_days >= useful_life_days:
                current_value = 0
            else:
                depreciation = float(asset.purchase_price) * (age_days / useful_life_days)
                current_value = float(asset.purchase_price) - depreciation
            
            asset.cached_current_value = max(current_value, 0)
            depreciation_list.append(asset)
            
        # Sort by Current Value (High to Low)
        depreciation_list.sort(key=lambda x: x.cached_current_value, reverse=True)
        context['financial_assets'] = depreciation_list[:50]
        
        # 2. EOL Candidates (> 4 Years Old)
        eol_threshold_date = today - timedelta(days=useful_life_days)
        context['eol_assets'] = Asset.objects.exclude(status='DISPOSED').filter(purchase_date__lt=eol_threshold_date).order_by('purchase_date')
        
        # 3. Top Maintenance Spenders
        context['top_maintenance_assets'] = Asset.objects.annotate(
            total_maint=Sum('maintenances__cost')
        ).filter(total_maint__gt=0).order_by('-total_maint')[:10]
        
        # 4. Disposed Assets Log
        context['disposed_assets'] = Asset.objects.filter(status__in=['DISPOSED', 'BROKEN']).order_by('-updated_at')[:50]
        
        return context

class SoftwareListView(LoginRequiredMixin, ListView):
    model = Software
    template_name = 'software/software_list.html'
    context_object_name = 'softwares'
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset().select_related('vendor', 'category')
        
        # Search
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | 
                Q(license_key__icontains=q) |
                Q(vendor__name__icontains=q)
            )
            
        # Filter by Type
        l_type = self.request.GET.get('type')
        if l_type:
            qs = qs.filter(license_type=l_type)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # KPI Stats
        all_sw = self.get_queryset()
        
        # 1. Financials
        context['total_spend'] = all_sw.aggregate(total=Sum('price'))['total'] or 0
        
        # 2. Compliance / Allocation
        # Need to know how many licenses are fully used or over-allocated (if possible)
        # We can sum seats_total and seats_used
        agg = all_sw.aggregate(total_seats=Sum('seats_total'), used_seats=Sum('seats_used'))
        total_seats = agg['total_seats'] or 0
        used_seats = agg['used_seats'] or 0
        
        if total_seats > 0:
            context['utilization_rate'] = int((used_seats / total_seats) * 100)
        else:
            context['utilization_rate'] = 0
            
        context['licenses_tracked'] = all_sw.count()
        
        # 3. Expiry Warning
        today = timezone.now().date()
        warning_date = today + timedelta(days=30)
        context['expiring_soon'] = all_sw.filter(expiry_date__lte=warning_date, expiry_date__gte=today).count()
        
        # Param passing
        context['current_type'] = self.request.GET.get('type', '')
        context['search_query'] = self.request.GET.get('q', '')
        
        return context

class SoftwareCreateView(LoginRequiredMixin, CreateView):
    model = Software
    form_class = SoftwareForm
    template_name = 'software/software_form.html'
    success_url = reverse_lazy('software_list')

class SoftwareUpdateView(LoginRequiredMixin, UpdateView):
    model = Software
    form_class = SoftwareForm
    template_name = 'software/software_form.html'
    success_url = reverse_lazy('software_list')

class SoftwareDetailView(LoginRequiredMixin, DetailView):
    model = Software
    template_name = 'software/software_detail.html'
    context_object_name = 'software'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allocations'] = self.object.allocations.select_related('employee', 'asset').all()
        return context

class SoftwareAllocationCreateView(LoginRequiredMixin, CreateView):
    model = SoftwareAllocation
    form_class = SoftwareAllocationForm
    template_name = 'software/software_allocation_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'software_pk' in self.kwargs:
            software = get_object_or_404(Software, pk=self.kwargs['software_pk'])
            context['software'] = software
        return context

    def get_initial(self):
        initial = super().get_initial()
        if 'software_pk' in self.kwargs:
            initial['software'] = get_object_or_404(Software, pk=self.kwargs['software_pk'])
        return initial

    def get_success_url(self):
         return reverse_lazy('software_list')

class SoftwareAllocationDeleteView(LoginRequiredMixin, DeleteView):
    model = SoftwareAllocation
    success_url = reverse_lazy('software_list')
    template_name = 'assets/confirm_delete.html' 

# Cloud Hosting & Domain Management Views

class CloudListView(LoginRequiredMixin, ListView):
    model = CloudAsset
    template_name = 'infrastructure/cloud_list.html'
    context_object_name = 'cloud_assets'
    ordering = ['expiry_date']

class CloudCreateView(LoginRequiredMixin, CreateView):
    model = CloudAsset
    form_class = CloudAssetForm
    template_name = 'infrastructure/cloud_form.html'
    success_url = reverse_lazy('cloud_list')

class CloudUpdateView(LoginRequiredMixin, UpdateView):
    model = CloudAsset
    form_class = CloudAssetForm
    template_name = 'infrastructure/cloud_form.html'
    success_url = reverse_lazy('cloud_list')

class CloudDeleteView(LoginRequiredMixin, DeleteView):
    model = CloudAsset
    success_url = reverse_lazy('cloud_list')
    template_name = 'assets/confirm_delete.html' 

# Unified Maintenance Module

class InfrastructureListView(LoginRequiredMixin, ListView):
    model = Infrastructure
    template_name = 'infrastructure/infra_list.html'
    context_object_name = 'infra_assets'
    ordering = ['-created_at'] # Assuming created_at exists or just name? Model doesn't have created_at actually.
    # Model has no created_at. ordering by infra_id or name.
    ordering = ['infra_id']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        is_manager = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        is_it_support = user.groups.filter(name='IT Support').exists()

        # 1. Location Data for Filter
        # Use hierarchy for cleaner dropdowns (Tree structure)
        
        if is_it_support and not is_manager:
            # SCOPED: Only show user's assigned location as a "Root"
            if hasattr(user, 'location') and user.location:
                # We wrap it in a list so the template loop works
                # Prefetch children to allow sub-location selection
                # Re-querying to ensure children are attached if user.location is stale or lazy
                user_loc = Location.objects.filter(pk=user.location.pk).prefetch_related('children').first()
                context['location_roots'] = [user_loc] if user_loc else []
            else:
                context['location_roots'] = []
        else:
            # FULL: Show actual roots
            context['location_roots'] = Location.objects.filter(parent__isnull=True).prefetch_related('children').order_by('name')
        
        # 2. Dynamic Summary Counts
        # Calculate counts for ALL types defined in choices to make it dynamic
        
        current_loc = self.request.GET.get('loc')
        
        qs_for_counts = Infrastructure.objects.all()
        
        # Apply Base Scope to Counts Query as well
        if is_it_support and not is_manager:
            if hasattr(user, 'location') and user.location:
                descendants = user.location.get_descendants(include_self=True)
                qs_for_counts = qs_for_counts.filter(location__in=descendants)
            else:
                qs_for_counts = qs_for_counts.none()

        if current_loc:
            # Hierarchy Logic: Get all descendants including self
            try:
                location = Location.objects.get(pk=current_loc)
                descendants = location.get_descendants(include_self=True)
                qs_for_counts = qs_for_counts.filter(location__in=descendants)
            except Location.DoesNotExist:
                 pass # Invalid ID, ignore

        # DYNAMIC COUNTS via InfrastructureType (New Relation)
        # 1. Get counts for each infra_type_id in current filter
        type_counts = qs_for_counts.values('infra_type').annotate(count=Count('id'))
        
        # 2. Convert to dict {infra_type_id: count}
        count_dict = {item['infra_type']: item['count'] for item in type_counts}
        
        # 3. Get all defined types (Cards)
        all_types = InfrastructureType.objects.filter(is_featured=True).order_by('name')
        
        # LEGACY MAPPING (Name -> Code)
        # To fix "Should be 2 but is 1", we count legacy types if infra_type is NULL
        legacy_counts = qs_for_counts.filter(infra_type__isnull=True).values('type').annotate(count=Count('id'))
        legacy_dict = {item['type']: item['count'] for item in legacy_counts}
        
        # Map common names to legacy codes
        name_map = {
            'Tower': ['TOWER'],
            'Server Rack': ['SERVER_RACK'],
            'Wallmount Rack': ['WALLMOUNT'],
            'Power Panel': ['PANEL', 'UPS', 'battery-full'],
            'Cabling': ['CABLING'],
            'Cooling': ['COOLING'],
        }

        summary_cards = []
        for t in all_types:
            count = count_dict.get(t.id, 0)
            
            # Hybrid: Add legacy count if name matches
            # This handles the transition period where items might have 'type' set but no 'infra_type'
            for key, codes in name_map.items():
                if key in t.name: # Flexible match, e.g. "Tower Nodes" matches "Tower"
                    for code in codes:
                        count += legacy_dict.get(code, 0)
            
            summary_cards.append({
                'code': t.slug, 
                'id': t.id,
                'label': t.name,
                'count': count,
                'icon': t.icon,
                'color': t.color
            })
        
        context['summary_cards'] = summary_cards
        context['all_infra_types'] = InfrastructureType.objects.all().order_by('name') # For Filter Dropdown
        context['current_type'] = self.request.GET.get('type', '')
        context['current_loc'] = int(current_loc) if current_loc and current_loc.isdigit() else None
        context['search_query'] = self.request.GET.get('q', '')
        context['today'] = timezone.now().date()
        
        # MAP VIEW LOGIC
        view_mode = self.request.GET.get('view', 'list')
        context['view_mode'] = view_mode
        
        if view_mode == 'map':
            # Serialize queryset for map
            # We need: name, lat, lng, type, status/color, detail_url, photo_url
            map_data = []
            for item in self.object_list: # Use full filtered list, not just page 1
                # Limit to items with coordinates
                if item.latitude and item.longitude:
                    map_data.append({
                        'name': item.name,
                        'lat': float(item.latitude),
                        'lng': float(item.longitude),
                        'type': item.infra_type.name if item.infra_type else item.get_type_display(),
                        'status': item.get_condition_display(),
                        'color': 'red' if item.condition in ['CRITICAL', 'POOR'] else 'green', # Simple logic
                        'url': item.get_absolute_url(),
                        'photo': item.photo.url if item.photo else None
                    })
            context['map_data_json'] = json.dumps(map_data)
        
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_manager = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        is_it_support = user.groups.filter(name='IT Support').exists()

        # SCOPE ENFORCEMENT
        if is_it_support and not is_manager:
            if hasattr(user, 'location') and user.location:
                descendants = user.location.get_descendants(include_self=True)
                queryset = queryset.filter(location__in=descendants)
            else:
                return queryset.none() # Assigned to nothing
        
        # Filter by Type (Dynamic Slug)
        # Filter by Type (Dynamic Slug + Legacy Fallback)
        req_type = self.request.GET.get('type')
        if req_type:
            type_obj = InfrastructureType.objects.filter(slug=req_type).first()
            if type_obj:
                # Legacy Mapping
                name_map = {
                    'Tower': ['TOWER'],
                    'Server Rack': ['SERVER_RACK'],
                    'Wallmount Rack': ['WALLMOUNT'],
                    'Power Panel': ['PANEL', 'UPS', 'battery-full'],
                    'Cabling': ['CABLING'],
                    'Cooling': ['COOLING'],
                }
                legacy_codes = []
                for key, codes in name_map.items():
                    if key in type_obj.name:
                        legacy_codes.extend(codes)
                
                if legacy_codes:
                    queryset = queryset.filter(Q(infra_type=type_obj) | Q(infra_type__isnull=True, type__in=legacy_codes))
                else:
                    queryset = queryset.filter(infra_type=type_obj)
            else:
                queryset = queryset.filter(infra_type__slug=req_type)
            
        # Filter by Location (Hierarchical)
        req_loc = self.request.GET.get('loc')
        if req_loc:
             try:
                 location = Location.objects.get(pk=req_loc)
                 descendants = location.get_descendants(include_self=True)
                 queryset = queryset.filter(location__in=descendants)
             except Location.DoesNotExist:
                 pass
            
        # Search
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(infra_id__icontains=query) |
                Q(location__name__icontains=query)
            )
            
        return queryset

class MaintenanceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'maintenance/maintenance_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        
        # 1. Corrective Maintenance (Asset Repairs)
        repairs = AssetMaintenance.objects.select_related('asset', 'technician').order_by('-scheduled_date')
        
        if query:
            repairs = repairs.filter(
                Q(maintenance_code__icontains=query) |
                Q(title__icontains=query) |
                Q(asset__name__icontains=query) |
                Q(maintenance_type__icontains=query)
            )
        
        context['recent_repairs'] = repairs[:100] # Increased limit, search handles specific finding
        
        # 2. Preventive Maintenance (Infrastructure Schedules)
        today = timezone.now().date()
        
        # Query InfraMaintenance directly
        # User requested to see Completed items too, so we removed the exclude(status='Completed') logic for the list
        schedules = InfraMaintenance.objects.select_related('infrastructure').order_by('scheduled_date')
        
        if query:
            schedules = schedules.filter(
                Q(maintenance_code__icontains=query) |
                Q(title__icontains=query) |
                Q(infrastructure__name__icontains=query) |
                Q(maintenance_type__icontains=query)
            )
        else:
            # If no search, maybe prioritize active/pending but still show history if needed?
            # User implies they want to see history. Let's just show all sorted by date.
            # To avoid overwhelming, maybe filter last 365 days if not searching? 
            # For now, let's keep it simple: Show all.
            pass
        
        context['upcoming_schedules'] = schedules
        
        # 3. KPI Cards Logic
        # A. Active Work Orders (Repairs In Progress or Scheduled)
        context['active_jobs_count'] = AssetMaintenance.objects.filter(
            Q(status='In Progress') | Q(status='Scheduled')
        ).count()
        
        # B. Monthly Cost (Current Month)
        context['monthly_cost'] = AssetMaintenance.objects.filter(
            scheduled_date__month=today.month,
            scheduled_date__year=today.year
        ).aggregate(total=Sum('cost'))['total'] or 0
        
        # C. Preventive Completion Ratio (This Month)
        monthly_preventive = InfraMaintenance.objects.filter(
            scheduled_date__month=today.month,
            scheduled_date__year=today.year
        )
        total_prev = monthly_preventive.count()
        completed_prev = monthly_preventive.filter(status='Completed').count()
        
        if total_prev > 0:
            context['preventive_completion'] = int((completed_prev / total_prev) * 100)
        else:
            context['preventive_completion'] = 0
            
        # D. Overdue (Existing)
        context['overdue_count'] = InfraMaintenance.objects.filter(scheduled_date__lt=today).exclude(status='Completed').count()
        
        context['today'] = today
        context['search_query'] = query
        context['active_tab'] = self.request.GET.get('tab') or 'repairs'
        
        return context

class MaintenanceExportView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="maintenance_report.xlsx"'
        
        wb = openpyxl.Workbook()
        
        # Sheet 1: Work Orders (Corrective)
        ws1 = wb.active
        ws1.title = "Work Orders"
        
        headers1 = ['Date', 'Code', 'Asset', 'Type', 'Issue/Title', 'Technician', 'Cost', 'Status']
        for col_num, header in enumerate(headers1, 1):
            cell = ws1.cell(row=1, column=col_num)
            cell.value = header
            cell.font = Font(bold=True)
            
        repairs = AssetMaintenance.objects.select_related('asset', 'technician').all().order_by('-scheduled_date')
        for row_num, item in enumerate(repairs, 2):
            ws1.cell(row=row_num, column=1).value = item.scheduled_date
            ws1.cell(row=row_num, column=2).value = item.maintenance_code
            ws1.cell(row=row_num, column=3).value = item.asset.name
            ws1.cell(row=row_num, column=4).value = item.maintenance_type
            ws1.cell(row=row_num, column=5).value = item.title
            ws1.cell(row=row_num, column=6).value = item.technician.get_full_name() if item.technician else 'Unassigned'
            ws1.cell(row=row_num, column=7).value = item.cost
            ws1.cell(row=row_num, column=8).value = item.status

        # Sheet 2: Preventive Schedules (Infrastructure)
        ws2 = wb.create_sheet(title="Infra Schedules")
        
        headers2 = ['Infra Name', 'Type', 'Location', 'Last Maint', 'Next Maint', 'Condition']
        for col_num, header in enumerate(headers2, 1):
            cell = ws2.cell(row=1, column=col_num)
            cell.value = header
            cell.font = Font(bold=True)
            
        schedules = Infrastructure.objects.exclude(next_maintenance_date__isnull=True).order_by('next_maintenance_date')
        for row_num, item in enumerate(schedules, 2):
            ws2.cell(row=row_num, column=1).value = item.name
            ws2.cell(row=row_num, column=2).value = item.get_type_display()
            ws2.cell(row=row_num, column=3).value = item.location.name if item.location else '-'
            ws2.cell(row=row_num, column=4).value = item.last_maintenance_date
            ws2.cell(row=row_num, column=5).value = item.next_maintenance_date
            ws2.cell(row=row_num, column=6).value = item.get_condition_display()

        return response 

# --- Maintenance CRUD Views ---

# Infra Views remain...
class InfraMaintenanceCreateView(LoginRequiredMixin, CreateView):
    model = InfraMaintenance
    form_class = InfraMaintenanceForm
    template_name = 'maintenance/maintenance_form.html'
    success_url = reverse_lazy('maintenance_dashboard')

    def get_initial(self):
        initial = super().get_initial()
        infra_id = self.request.GET.get('infra')
        if infra_id:
            initial['infrastructure'] = get_object_or_404(Infrastructure, pk=infra_id)
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.GET.get('infra'):
            form.fields['infrastructure'].widget = forms.HiddenInput()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        infra_id = self.request.GET.get('infra')
        if infra_id:
            context['infrastructure'] = get_object_or_404(Infrastructure, pk=infra_id)
        context['action_title'] = "Add Generic/Infra Maintenance"
        return context

    def form_valid(self, form):
        # Ensure infrastructure is set if hidden/initial
        # The form should handle it if passed in initial and field is present but hidden
        # But if it wasn't in the form data (disabled/excluded), we set it here.
        # Check standard behavior first. If widget is HiddenInput, it submits value.
        # Just to be safe/explicit if URL param overrides:
        infra_id = self.request.GET.get('infra')
        if infra_id and not form.instance.infrastructure_id:
             form.instance.infrastructure = get_object_or_404(Infrastructure, pk=infra_id)
             
        form.instance.maintenance_code = '' # Trigger auto-gen
        return super().form_valid(form)

class InfraMaintenanceUpdateView(LoginRequiredMixin, UpdateView):
    model = InfraMaintenance
    form_class = InfraMaintenanceForm
    template_name = 'maintenance/maintenance_form.html'
    success_url = reverse_lazy('maintenance_dashboard')

    def form_valid(self, form):
        if form.instance.status == 'Completed' and not form.instance.completed_date:
            form.instance.completed_date = timezone.now().date()
        return super().form_valid(form)

class InfraMaintenanceDeleteView(LoginRequiredMixin, DeleteView):
    model = InfraMaintenance
    success_url = reverse_lazy('maintenance_dashboard')
    template_name = 'assets/confirm_delete.html'

class InfrastructureCreateView(LoginRequiredMixin, CreateView):
    model = Infrastructure
    form_class = InfrastructureForm
    template_name = 'infrastructure/infra_form.html'
    success_url = reverse_lazy('infra_list')

class InfrastructureUpdateView(LoginRequiredMixin, UpdateView):
    model = Infrastructure
    form_class = InfrastructureForm
    template_name = 'infrastructure/infra_form.html'
    success_url = reverse_lazy('infra_list')

class InfrastructureDeleteView(LoginRequiredMixin, DeleteView):
    model = Infrastructure
    success_url = reverse_lazy('infra_list')
    template_name = 'assets/confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('infra_list')
        return context

class InfrastructureDetailView(LoginRequiredMixin, DetailView):
    model = Infrastructure
    template_name = 'infrastructure/infra_detail.html'
    context_object_name = 'infrastructure'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Maintenance History
        context['maintenance_history'] = InfraMaintenance.objects.filter(infrastructure=self.object).order_by('-scheduled_date')
        # Available assets for quick linking
        context['unlinked_assets'] = Asset.objects.filter(infrastructure__isnull=True).order_by('name')
        return context

class InfrastructureLinkAssetView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        infrastructure = get_object_or_404(Infrastructure, pk=pk)
        action = request.POST.get('action')
        asset_id = request.POST.get('asset_id')
        
        if not asset_id:
            messages.error(request, "No asset selected.")
            return redirect('infra_detail', pk=pk)
            
        asset = get_object_or_404(Asset, pk=asset_id)
        
        if action == 'link':
            asset.infrastructure = infrastructure
            asset.save()
            messages.success(request, f"Asset '{asset.name}' linked to {infrastructure.name}.")
        elif action == 'unlink':
            if asset.infrastructure == infrastructure:
                asset.infrastructure = None
                asset.save()
                messages.success(request, f"Asset '{asset.name}' unlinked from {infrastructure.name}.")
                
        return redirect('infra_detail', pk=pk)

class InfrastructurePrintLabelView(LoginRequiredMixin, DetailView):
    model = Infrastructure
    template_name = 'infrastructure/infra_print_label.html'
    context_object_name = 'infrastructure'

class BulkInfraLabelView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        selected_ids = request.POST.getlist('selected_items')
        
        if not selected_ids:
            messages.error(request, "No items selected.")
            return redirect('infra_list')

        infrastructures = Infrastructure.objects.filter(id__in=selected_ids)
        return render(request, 'infrastructure/infra_print_labels_bulk.html', {
            'infrastructures': infrastructures
        })
# ==========================================
# CONTRACT MANAGEMENT (Phase 43)
# ==========================================

class ContractListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = 'assets/contract_list.html'
    context_object_name = 'contracts'
    ordering = ['end_date']
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().filter(replaced_by__isnull=True)
        
        # Filtering
        contract_type = self.request.GET.get('type')
        vendor_id = self.request.GET.get('vendor')
        search_query = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if contract_type:
            qs = qs.filter(contract_type=contract_type)
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        if status:
            qs = qs.filter(status=status)
            
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) | 
                Q(vendor__name__icontains=search_query) |
                Q(notes__icontains=search_query)
            )
            
        return qs

    def get_paginate_by(self, queryset):
        if self.request.GET.get('print') == '1':
            return None
        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filters Data
        context['vendors'] = Vendor.objects.filter(contracts__isnull=False).distinct()
        context['contract_types'] = Contract.TYPE_CHOICES
        
        # KPIS
        today = timezone.now().date()
        base_qs = Contract.objects.filter(replaced_by__isnull=True)
        
        context['total_value'] = base_qs.exclude(status='CANCELLED').aggregate(total=Sum('cost'))['total'] or 0
        context['active_count'] = base_qs.filter(status='ACTIVE').count()
        context['expiring_soon_count'] = base_qs.filter(
            end_date__lte=today + timedelta(days=30),
            end_date__gte=today
        ).count()
        
        return context

class ContractDetailView(LoginRequiredMixin, DetailView):
    model = Contract
    template_name = 'assets/contract_detail.html'
    context_object_name = 'contract'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['history'] = self.object.get_history()
        return context

class ContractCreateView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'assets/contract_form.html'
    success_url = reverse_lazy('contract_list')

    def form_valid(self, form):
        messages.success(self.request, f"Contract '{form.instance.title}' created successfully.")
        return super().form_valid(form)

class ContractUpdateView(LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = 'assets/contract_form.html'
    success_url = reverse_lazy('contract_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Contract '{form.instance.title}' updated successfully.")
        return super().form_valid(form)

class ContractDeleteView(LoginRequiredMixin, DeleteView):
    model = Contract
    template_name = 'assets/contract_confirm_delete.html'
    success_url = reverse_lazy('contract_list')

class ContractRenewView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'assets/contract_form.html'
    success_url = reverse_lazy('contract_list')

    def get_initial(self):
        initial = super().get_initial()
        # Get old contract
        old_contract = get_object_or_404(Contract, pk=self.kwargs['pk'])
        # Pre-fill
        initial['title'] = old_contract.title
        initial['vendor'] = old_contract.vendor_id
        initial['contract_type'] = old_contract.contract_type
        initial['billing_cycle'] = old_contract.billing_cycle
        initial['cost'] = old_contract.cost
        initial['auto_renew'] = old_contract.auto_renew
        initial['notify_days_before'] = old_contract.notify_days_before
        initial['notes'] = old_contract.notes
        return initial

    def form_valid(self, form):
        old_contract = get_object_or_404(Contract, pk=self.kwargs['pk'])
        
        # Overlap Prevention: Adjust end date of old contract if needed
        if form.instance.start_date <= old_contract.end_date:
            old_contract.end_date = form.instance.start_date - timedelta(days=1)
            
        # Update old contract status
        old_contract.status = 'PAID'
        old_contract.save()
        
        form.instance.previous_contract = old_contract
        messages.success(self.request, f"Contract '{form.instance.title}' renewed successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_renewal'] = True
        context['old_contract'] = get_object_or_404(Contract, pk=self.kwargs['pk'])
        return context

# -----------------------------------------------------------------------------
# Location / Branch Command Center Views
# -----------------------------------------------------------------------------

class LocationTreeView(LoginRequiredMixin, TemplateView):
    template_name = 'assets/location_tree.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch all locations ordered by hierarchy (Root first, then children)
        # We fetch all and let the template or Python build the tree
        locations = Location.objects.all().order_by('parent_id', 'name')
        
        # We can build a simple tree structure here if needed, or pass flat list
        # Scoped Visibility Logic
        user = self.request.user
        is_manager = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        is_it_support = user.groups.filter(name='IT Support').exists()

        if is_it_support and not is_manager:
            if hasattr(user, 'location') and user.location:
                # Show ONLY the user's location branch
                root_nodes = [user.location]
            else:
                # IT Support with no location? Show nothing.
                root_nodes = []
                messages.warning(self.request, "Please set your location in Profile to view Branch/Locations.")
        else:
            # Show Full Tree
            root_nodes = locations.filter(parent__isnull=True)
            
        context['root_nodes'] = root_nodes
        context['all_locations'] = locations 
        context['is_manager'] = is_manager
        return context

class LocationDetailAjaxView(LoginRequiredMixin, DetailView):
    model = Location
    template_name = 'assets/partials/location_detail.html'
    context_object_name = 'location'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loc = self.object
        
        # 1. Total Assets in this location (and optionally children? Let's stick to direct first, or hierarchical if agreed)
        # User agreed on Hierarchical concept. So let's count hierarchical.
        # Get self and descendants
        
        # Helper to get all descendant IDs (simple recursive)
        def get_descendant_ids(location):
            ids = [location.id]
            for child in location.children.all():
                ids.extend(get_descendant_ids(child))
            return ids
            
        relevant_ids = get_descendant_ids(loc)
        
        assets_q = Asset.objects.filter(location_id__in=relevant_ids)
        
        context['total_assets'] = assets_q.count()
        context['total_value'] = assets_q.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
        context['good_assets'] = assets_q.filter(status='IN_USE').count()
        context['broken_assets'] = assets_q.filter(status='BROKEN').count()
        
        # 2. Staff Assigned
        from django.contrib.auth import get_user_model
        User = get_user_model()
        staff_qs = User.objects.filter(location_id__in=relevant_ids).annotate(
            asset_count=Count('assigned_assets', distinct=True),
            ticket_count=Count('tickets_created', distinct=True)
        )
        context['staff_list'] = staff_qs
        context['total_users'] = staff_qs.count()
        
        user = self.request.user
        context['is_manager'] = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()
        
        from core.license import check_location_limit
        context['can_add_location'] = check_location_limit()
        
        return context

class LocationCreateView(LoginRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'assets/location_form.html'
    success_url = reverse_lazy('location_tree')

    def get_initial(self):
        initial = super().get_initial()
        # Pre-fill parent if provided in GET (e.g. "Add Sub-Branch" button)
        parent_id = self.request.GET.get('parent')
        if parent_id:
             initial['parent'] = parent_id
        return initial

    def form_valid(self, form):
        from core.license import check_location_limit
        if not check_location_limit():
             messages.error(self.request, "License Restriction: Essential Edition supports only 1 Location. Upgrade to Enterprise.")
             return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

class LocationUpdateView(LoginRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'assets/location_form.html'
    success_url = reverse_lazy('location_tree')

class LocationDeleteView(LoginRequiredMixin, DeleteView):
    model = Location
    template_name = 'assets/confirm_delete.html'
    success_url = reverse_lazy('location_tree')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Delete Location"
        context['warning'] = "Warning: Deleting this location might affect Assets assigned to it. Please check before deleting."
        return context
class AssetPrintListView(AssetListView):
    template_name = 'assets/asset_print_list.html'
    paginate_by = 500  # Large page size for print report

    def get_queryset(self):
        qs = super().get_queryset()
        # Force ordering by category name for regrouping in the template
        return qs.order_by('category__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fix for template relying on 'mode' variable vs 'view_mode'
        context['mode'] = self.request.GET.get('mode', 'operational')
        
        # Add selection objects for Header Display
        loc_id = self.request.GET.get('loc')
        if loc_id:
            try:
                context['selected_location'] = Location.objects.get(id=loc_id)
            except Location.DoesNotExist:
                pass
        
        dept_id = self.request.GET.get('dept')
        if dept_id:
             try:
                context['selected_department'] = Department.objects.get(id=dept_id)
             except Department.DoesNotExist:
                pass
        
        cat_id = self.request.GET.get('category')
        if cat_id:
            try:
                context['selected_category'] = Category.objects.get(id=cat_id)
            except Category.DoesNotExist:
                pass
                
        return context
class PartHistoryCreateView(LoginRequiredMixin, CreateView):
    model = PartHistory
    form_class = PartHistoryForm
    template_name = 'assets/part_history_form.html'
    
    def form_valid(self, form):
        asset = get_object_or_404(Asset, pk=self.kwargs['asset_id'])
        form.instance.asset = asset
        messages.success(self.request, f"Part history added for '{asset.name}'.")
        return super().form_valid(form)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset'] = get_object_or_404(Asset, pk=self.kwargs['asset_id'])
        return context

    def get_success_url(self):
        return reverse('asset_detail', kwargs={'pk': self.kwargs['asset_id']}) + '#part-history'

class PartHistoryDeleteView(LoginRequiredMixin, DeleteView):
    model = PartHistory
    template_name = 'assets/confirm_delete.html'
    
    def get_success_url(self):
        asset_id = self.object.asset.id
        messages.success(self.request, "Part history record deleted.")
        return reverse('asset_detail', kwargs={'pk': asset_id}) + '#part-history'

# --- Category Management Views ---
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'assets/category_list.html'
    context_object_name = 'categories'
    ordering = ['name']

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    fields = ['name', 'type']
    template_name = 'assets/category_form.html'
    success_url = reverse_lazy('category_list')

    def form_valid(self, form):
        messages.success(self.request, "Category created successfully.")
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    fields = ['name', 'type']
    template_name = 'assets/category_form.html'
    success_url = reverse_lazy('category_list')

    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully.")
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'assets/confirm_delete.html'
    success_url = reverse_lazy('category_list')

    def delete(self, request, *args, **kwargs):
        # DEMO MODE: Block delete
        from django.conf import settings
        if getattr(settings, 'DEMO_MODE', False):
            messages.error(request, "This action is disabled in Demo Mode.")
            return redirect('category_list')
        messages.success(request, "Category deleted successfully.")
        return super().delete(request, *args, **kwargs)

from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.views import View

class AssetResolveCodeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', '').strip()
        if code:
            asset = Asset.objects.filter(asset_code=code).first()
            if asset:
                return redirect('asset_detail', pk=asset.pk)
        messages.error(request, f'Asset dengan kode {code} tidak ditemukan.')
        return redirect('asset_scanner')



# --- Asset Inspection and Document Management ---

class AssetInspectionPrintView(LoginRequiredMixin, DetailView):
    model = Asset
    template_name = 'assets/asset_inspection_print.html'
    context_object_name = 'asset'

class AssetDocumentUploadView(LoginRequiredMixin, CreateView):
    model = AssetDocument
    form_class = AssetDocumentForm
    template_name = 'assets/document_upload_modal.html'

    def form_valid(self, form):
        form.instance.asset_id = self.kwargs['asset_id']
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, 'Document uploaded successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('asset_detail', kwargs={'pk': self.kwargs['asset_id']}) + '#documents'

class AssetDocumentDeleteView(LoginRequiredMixin, DeleteView):
    model = AssetDocument

    def get_success_url(self):
        messages.success(self.request, 'Document deleted successfully.')
        return reverse('asset_detail', kwargs={'pk': self.object.asset_id}) + '#documents'

from django.http import JsonResponse
from django.views import View

class CapexDataAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        period = request.GET.get('period', '6m')
        loc_id = request.GET.get('loc')
        
        from .models import Asset, Location
        assets = Asset.objects.all()
        if loc_id:
            try:
                selected_location = Location.objects.get(pk=loc_id)
                descendants = selected_location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                assets = assets.filter(location_id__in=descendant_ids)
            except Location.DoesNotExist:
                pass
                
        import datetime
        from django.utils import timezone
        today = timezone.now().date()
        
        if period == '3m':
            start_date = today - datetime.timedelta(days=90)
        elif period == '6m':
            start_date = today - datetime.timedelta(days=180)
        elif period == '1y':
            start_date = today - datetime.timedelta(days=365)
        elif period == 'all':
            start_date = None
        else: # ytd
            start_date = datetime.date(today.year, 1, 1)

        if start_date:
            recent_assets = assets.filter(purchase_date__gte=start_date, purchase_price__isnull=False)
        else:
            recent_assets = assets.filter(purchase_price__isnull=False)
            
        from collections import defaultdict
        capex_monthly = defaultdict(float)
        
        for a in recent_assets:
            if a.purchase_date:
                month_label = a.purchase_date.strftime("%b %Y")
                capex_monthly[month_label] += float(a.purchase_price)
                
        sorted_capex_months = sorted(capex_monthly.keys(), key=lambda d: datetime.datetime.strptime(d, "%b %Y"))
        
        return JsonResponse({
            'labels': sorted_capex_months,
            'data': [capex_monthly[m] for m in sorted_capex_months],
            'total': sum(capex_monthly.values())
        })

class MaintenancePivotAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        loc_id = request.GET.get('loc')
        
        from maintenance.models import AssetMaintenance
        from assets.models import Location
        
        maintenances = AssetMaintenance.objects.select_related('asset', 'asset__category', 'asset__location', 'asset__department', 'asset__assigned_to', 'technician', 'vendor').all()
        
        if loc_id:
            try:
                selected_location = Location.objects.get(pk=loc_id)
                descendants = selected_location.get_descendants(include_self=True)
                descendant_ids = [loc.id for loc in descendants]
                maintenances = maintenances.filter(asset__location_id__in=descendant_ids)
            except Location.DoesNotExist:
                pass
                
        year_filter = request.GET.get('year')
        if year_filter and year_filter != 'all':
            maintenances = maintenances.filter(scheduled_date__year=int(year_filter))
                
        data = []
        for m in maintenances:
            data.append({
                "Asset": m.asset.name if m.asset else "Unknown",
                "Asset ID": m.asset.asset_code if m.asset else "-",
                "Category": m.asset.category.name if m.asset and m.asset.category else "Uncategorized",
                "Location": m.asset.location.name if m.asset and m.asset.location else "Unknown",
                "Department": m.asset.department.name if m.asset and m.asset.department else "-",
                "User": m.asset.assigned_to.get_full_name() or m.asset.assigned_to.username if m.asset and m.asset.assigned_to else "-",
                "Type": m.maintenance_type,
                "Status": m.status,
                "Technician": m.technician.get_full_name() or m.technician.username if m.technician else "-",
                "Vendor": m.vendor.name if m.vendor else "-",
                "Cost": float(m.cost) if m.cost else 0.0,
                "Year": m.scheduled_date.strftime("%Y") if m.scheduled_date else "",
                "Month": m.scheduled_date.strftime("%b %Y") if m.scheduled_date else "",
                "Date": m.scheduled_date.strftime("%Y-%m-%d") if m.scheduled_date else ""
            })
            
        # Add PartHistory records
        from assets.models import PartHistory
        parts = PartHistory.objects.select_related('asset', 'asset__category', 'asset__location', 'asset__department', 'asset__assigned_to', 'vendor').all()
        
        if loc_id and 'descendant_ids' in locals():
            parts = parts.filter(asset__location_id__in=descendant_ids)
            
        if year_filter and year_filter != 'all':
            parts = parts.filter(action_date__year=int(year_filter))
            
        for p in parts:
            data.append({
                "Asset": p.asset.name if p.asset else "Unknown",
                "Asset ID": p.asset.asset_code if p.asset else "-",
                "Category": p.asset.category.name if p.asset and p.asset.category else "Uncategorized",
                "Location": p.asset.location.name if p.asset and p.asset.location else "Unknown",
                "Department": p.asset.department.name if p.asset and p.asset.department else "-",
                "User": p.asset.assigned_to.get_full_name() or p.asset.assigned_to.username if p.asset and p.asset.assigned_to else "-",
                "Type": "Part Replacement",
                "Status": "Completed",
                "Technician": "-",
                "Vendor": p.vendor.name if p.vendor else "-",
                "Cost": float(p.cost) if p.cost else 0.0,
                "Year": p.action_date.strftime("%Y") if p.action_date else "",
                "Month": p.action_date.strftime("%b %Y") if p.action_date else "",
                "Date": p.action_date.strftime("%Y-%m-%d") if p.action_date else ""
            })
            
        return JsonResponse(data, safe=False)
