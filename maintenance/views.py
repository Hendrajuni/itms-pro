from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Q
from itertools import chain
from .models import AssetMaintenance, InfraMaintenance

class MaintenanceDashboardView(LoginRequiredMixin, ListView):
    template_name = 'maintenance/maintenance_list.html'
    context_object_name = 'asset_logs'

    def get_queryset(self):
        # We'll use get_context_data for the main logic, but ListView needs a queryset
        return AssetMaintenance.objects.all().select_related('asset', 'technician').order_by('scheduled_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        current_month = today.month
        current_year = today.year

        # --- Filters ---
        status_filter = self.request.GET.get('status')
        location_filter = self.request.GET.get('location')

        # Base Queries
        asset_qs = AssetMaintenance.objects.select_related('asset', 'technician').order_by('scheduled_date')
        infra_qs = InfraMaintenance.objects.select_related('infrastructure', 'technician').order_by('scheduled_date')

        # Apply Filters
        if status_filter:
            asset_qs = asset_qs.filter(status=status_filter)
            infra_qs = infra_qs.filter(status=status_filter)
        
        if location_filter:
            asset_qs = asset_qs.filter(asset__location_id=location_filter)
            # Assuming Infrastructure has a location field or similar relation
            if hasattr(InfraMaintenance, 'infrastructure'):
                 infra_qs = infra_qs.filter(infrastructure__location_id=location_filter)

        # --- KPI Calculation (Pre-filter or Post-filter? User usually wants Contextual KPIs, but "Dashboard" usually means global. 
        # Let's keep KPIs global (unfiltered) or make them respect filter? 
        # Standard pattern: KPIs are high-level, tables are drilled down. Let's keep KPIs global for now to avoid confusion unless requested.)
        
        # Re-fetching GLOBAL for KPIs
        global_asset_logs = AssetMaintenance.objects.all()
        global_infra_logs = InfraMaintenance.objects.all()

        def count_kpi(model_qs):
            return {
                'overdue': model_qs.filter(scheduled_date__lt=today).exclude(status='Completed').count(),
                'today': model_qs.filter(scheduled_date=today).count(),
                'progress': model_qs.filter(status='In Progress').count(),
                'completed': model_qs.filter(status='Completed', completed_date__month=current_month, completed_date__year=current_year).count()
            }

        asset_kpis = count_kpi(global_asset_logs)
        infra_kpis = count_kpi(global_infra_logs)

        context['overdue_count'] = asset_kpis['overdue'] + infra_kpis['overdue']
        context['today_count'] = asset_kpis['today'] + infra_kpis['today']
        context['progress_count'] = asset_kpis['progress'] + infra_kpis['progress']
        context['completed_count'] = asset_kpis['completed'] + infra_kpis['completed']

        # --- Pagination ---
        from django.core.paginator import Paginator
        
        # Asset Pagination
        asset_paginator = Paginator(asset_qs, 10) 
        asset_page_number = self.request.GET.get('asset_page')
        asset_page_obj = asset_paginator.get_page(asset_page_number)
        
        # Infra Pagination
        infra_paginator = Paginator(infra_qs, 10)
        infra_page_number = self.request.GET.get('infra_page')
        infra_page_obj = infra_paginator.get_page(infra_page_number)

        context['asset_logs'] = asset_page_obj
        context['infra_logs'] = infra_page_obj
        
        # Filter Options
        from assets.models import Location 
        context['locations'] = Location.objects.all()
        context['status_choices'] = AssetMaintenance.STATUS_CHOICES
        
        return context
