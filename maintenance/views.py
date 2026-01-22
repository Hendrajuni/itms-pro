from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class MaintenanceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/under_construction.html'
