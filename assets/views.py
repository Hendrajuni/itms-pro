from django.shortcuts import render, get_object_or_404
from django import forms
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
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

from .models import Asset, AssetSpecification, NetworkInterface, AssetLoan, Software, SoftwareAllocation, CloudAsset, Infrastructure, Contract, Location, Department, Category, AssetStorage
from governance.models import DailyLog, Project
from maintenance.models import AssetMaintenance, InfraMaintenance
from .forms import AssetForm, AssetNoteForm, NetworkInterfaceFormSet, AssetStorageFormSet, SoftwareAllocationFormSet, AssetLoanForm, AssetMaintenanceForm, InfraMaintenanceForm, SoftwareForm, SoftwareAllocationForm, CloudAssetForm, InfrastructureForm, ContractForm
from django.db.models import Sum, Q, Count, F
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

class AssetListView(LoginRequiredMixin, ListView):
    model = Asset
    template_name = 'assets/asset_list.html'
    context_object_name = 'assets'
    ordering = ['-created_at']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('category', 'assigned_to', 'department', 'location')
        
        # Filter: Location
        loc = self.request.GET.get('loc')
        if loc:
            queryset = queryset.filter(location_id=loc)
            
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
        direction = self.request.GET.get('order', 'desc')
        
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
        # Check if user is in 'IT Support' group for UI logic
        context['is_it_support'] = self.request.user.groups.filter(name='IT Support').exists()
        
        # Filters Data
        context['locations'] = Location.objects.all()
        context['departments'] = Department.objects.all()
        
        # Category Counts for Sidebar
        # Only show categories that have at least one asset
        context['category_counts'] = Category.objects.annotate(
            asset_count=Count('assets')
        ).filter(asset_count__gt=0).order_by('name')
        
        # View Mode Logic
        view_mode = self.request.GET.get('mode', 'operational')
        context['view_mode'] = view_mode
        context['current_sort'] = self.request.GET.get('sort', 'created')
        context['current_order'] = self.request.GET.get('order', 'desc')
        context['current_category'] = self.request.GET.get('category')
        
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
        assets = Asset.objects.filter(id__in=asset_ids).select_related('assigned_to', 'location')
        
        context = {
            'assets': assets,
            'print_date': timezone.now()
        }
        return render(request, 'assets/print_labels_bulk.html', context)

class AssetCreateView(LoginRequiredMixin, CreateView):
    model = Asset
    form_class = AssetForm
    template_name = 'assets/asset_form.html'
    success_url = reverse_lazy('asset_list')
    
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['network_interfaces'] = NetworkInterfaceFormSet(self.request.POST)
            data['storage_formset'] = AssetStorageFormSet(self.request.POST)
            data['software_formset'] = SoftwareAllocationFormSet(self.request.POST)
        else:
            data['network_interfaces'] = NetworkInterfaceFormSet()
            data['storage_formset'] = AssetStorageFormSet()
            data['software_formset'] = SoftwareAllocationFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        network_interfaces = context['network_interfaces']
        storage_formset = context['storage_formset']
        software_formset = context['software_formset']
        self.object = form.save()
        
        if network_interfaces.is_valid() and storage_formset.is_valid() and software_formset.is_valid():
            network_interfaces.instance = self.object
            network_interfaces.save()
            storage_formset.instance = self.object
            storage_formset.save()
            software_formset.instance = self.object
            software_formset.save()
        else:
             return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

class AssetUpdateView(LoginRequiredMixin, UpdateView):
    model = Asset
    form_class = AssetForm
    template_name = 'assets/asset_form.html'
    success_url = reverse_lazy('asset_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
             data['network_interfaces'] = NetworkInterfaceFormSet(self.request.POST, instance=self.object)
             data['storage_formset'] = AssetStorageFormSet(self.request.POST, instance=self.object)
             data['software_formset'] = SoftwareAllocationFormSet(self.request.POST, instance=self.object)
        else:
             data['network_interfaces'] = NetworkInterfaceFormSet(instance=self.object)
             data['storage_formset'] = AssetStorageFormSet(instance=self.object)
             data['software_formset'] = SoftwareAllocationFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        network_interfaces = context['network_interfaces']
        storage_formset = context['storage_formset']
        software_formset = context['software_formset']
        self.object = form.save()
        
        if network_interfaces.is_valid() and storage_formset.is_valid() and software_formset.is_valid():
             network_interfaces.instance = self.object
             network_interfaces.save()
             storage_formset.instance = self.object
             storage_formset.save()
             software_formset.instance = self.object
             software_formset.save()
        else:
             return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)

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
        context['history'] = self.object.loans.all().order_by('-loan_date') if hasattr(self.object, 'loans') else []
        
        maintenance_logs = self.object.maintenances.all().order_by('-scheduled_date') if hasattr(self.object, 'maintenances') else []
        # Note: 'maintenances' related name might default to assetmaintenance_set if not defined explicitly.
        # But our previous edits used related_name='maintenances' (or we assumed so).
        # Let's handle safe lookup.
        
        context['maintenance_logs'] = maintenance_logs
        
        # Calculate total cost
        total_cost = sum(log.cost for log in maintenance_logs)
        context['total_maintenance_cost'] = total_cost
        
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

class AssetDetailPrintView(LoginRequiredMixin, DetailView):
    model = Asset
    template_name = 'assets/print_asset_detail.html'
    context_object_name = 'asset'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Populate context similar to detail view for report
        context['history'] = self.object.loans.all().order_by('-loan_date') if hasattr(self.object, 'loans') else []
        
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
    template_name = 'assets/asset_action_form.html'

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
    template_name = 'assets/asset_action_form.html'
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

class AssetAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'assets/asset_analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. KPI Cards
        context['total_assets'] = Asset.objects.count()
        context['total_value'] = Asset.objects.aggregate(total=Sum('purchase_price'))['total'] or 0
        context['total_maintenance_cost'] = AssetMaintenance.objects.aggregate(total=Sum('cost'))['total'] or 0
        context['assets_broken'] = Asset.objects.filter(status='BROKEN').count()
        
        # 2. Charts Data
        
        # A. By Category
        cat_data = Asset.objects.values('category__name').annotate(count=Count('id')).order_by('-count')
        context['chart_category_labels'] = json.dumps([item['category__name'] for item in cat_data])
        context['chart_category_data'] = json.dumps([item['count'] for item in cat_data])
        
        # B. By Location (Top 10)
        loc_data = Asset.objects.values('location__name').annotate(count=Count('id')).order_by('-count')[:10]
        context['chart_location_labels'] = json.dumps([item['location__name'] for item in loc_data])
        context['chart_location_data'] = json.dumps([item['count'] for item in loc_data])
        
        # C. Purchase Trends (By Year)
        trend_data = Asset.objects.annotate(year=ExtractYear('purchase_date')).values('year').annotate(count=Count('id')).order_by('year')
        # Filter out None years if any
        trend_data = [item for item in trend_data if item['year'] is not None]
        context['chart_trend_labels'] = json.dumps([item['year'] for item in trend_data])
        context['chart_trend_data'] = json.dumps([item['count'] for item in trend_data])
        
        # 3. Tables
        context['recent_purchases'] = Asset.objects.order_by('-purchase_date')[:5]
        
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
        return super().get_queryset().select_related('vendor', 'category')

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
        
        # Summary Counts
        # Constructing querysets for counts efficiently? 
        # Better to do distinct counts? Or just simple filters.
        # We need counts of ALL items, not just filtered ones, for the top cards.
        qs = Infrastructure.objects.all()
        context['tower_count'] = qs.filter(type='TOWER').count()
        context['rack_count'] = qs.filter(type='SERVER_RACK').count()
        context['wallmount_count'] = qs.filter(type='WALLMOUNT').count()
        context['panel_count'] = qs.filter(type='PANEL').count()
        
        context['current_type'] = self.request.GET.get('type', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['today'] = timezone.now().date()
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by Type
        req_type = self.request.GET.get('type')
        if req_type:
            queryset = queryset.filter(type=req_type)
            
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
        return context

# ==========================================
# CONTRACT MANAGEMENT (Phase 43)
# ==========================================

class ContractListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = 'assets/contract_list.html'
    context_object_name = 'contracts'
    ordering = ['end_date']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # KPIS
        today = timezone.now().date()
        context['total_value'] = Contract.objects.exclude(status='CANCELLED').aggregate(total=Sum('cost'))['total'] or 0
        context['active_count'] = Contract.objects.filter(status='ACTIVE').count()
        context['expiring_soon_count'] = Contract.objects.filter(
            end_date__lte=today + timedelta(days=30),
            end_date__gte=today
        ).count()
        
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        type_ = self.request.GET.get('type')
        
        if status:
            qs = qs.filter(status=status)
        if type_:
            qs = qs.filter(contract_type=type_)
            
        return qs

class ContractDetailView(LoginRequiredMixin, DetailView):
    model = Contract
    template_name = 'assets/contract_detail.html'
    context_object_name = 'contract'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add logic here if we link contracts to assets directly (ManyToMany)
        # For now, just basic details
        return context

class ContractCreateView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'assets/contract_form.html'
    success_url = reverse_lazy('contract_list')

class ContractUpdateView(LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = 'assets/contract_form.html'
    success_url = reverse_lazy('contract_list')

class ContractDeleteView(LoginRequiredMixin, DeleteView):
    model = Contract
    template_name = 'assets/contract_confirm_delete.html'
    success_url = reverse_lazy('contract_list')
