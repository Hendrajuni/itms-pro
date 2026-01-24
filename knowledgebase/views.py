from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from .models import Article
from .forms import ArticleForm # Need to create this form

class ITStaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'IT Support']).exists()

class ArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = 'knowledgebase/article_list.html'
    context_object_name = 'articles'
    paginate_by = 10
    
    def get_queryset(self):
        user = self.request.user
        is_it = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'IT Support']).exists()
        
        # IT Staff sees everything (including Drafts?), No, list restricts to Published unless specified?
        # Let's say: 
        # IT Staff -> All Published (Internal/Public). Can see Drafts in a separate "My Drafts" or "Manage" view?
        # For Main List, let's show Published.
        
        queryset = Article.objects.filter(status='PUBLISHED')
        
        if not is_it:
            # Normal users: Only Public
            queryset = queryset.filter(visibility='PUBLIC')
            
        # Filters
        cat = self.request.GET.get('category')
        if cat:
            queryset = queryset.filter(category=cat)
            
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | 
                Q(content__icontains=q)
            )
            
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Article.CATEGORY_CHOICES
        user = self.request.user
        # Logic moved from template to view for reliability
        # STRICT CHECK: Only Superuser or specific Groups.
        # Removed user.is_staff to prevent regular staff users from creating articles.
        can_create = user.is_superuser or user.groups.filter(name__in=['IT Support', 'Admin', 'Administrator', 'Manager']).exists()
        context['can_create_article'] = can_create
        return context

class ArticleDetailView(LoginRequiredMixin, DetailView):
    model = Article
    template_name = 'knowledgebase/article_detail.html'
    
    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        is_it = user.is_superuser or user.groups.filter(name__in=['Administrator', 'Manager', 'IT Support']).exists()
        
        if obj.visibility == 'INTERNAL' and not is_it:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to view this internal article.")
            
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        can_edit = user.is_superuser or user.groups.filter(name__in=['IT Support', 'Admin', 'Administrator', 'Manager']).exists()
        context['can_edit_article'] = can_edit
        
        # Increment View Count (simple logic)
        self.object.views_count += 1
        self.object.save()
        return context

class ArticleCreateView(LoginRequiredMixin, ITStaffRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'knowledgebase/article_form.html'
    success_url = reverse_lazy('article_list')
    
    def get_initial(self):
        initial = super().get_initial()
        asset_id = self.request.GET.get('asset_id')
        if asset_id:
            from assets.models import Asset
            try:
                asset = Asset.objects.get(pk=asset_id)
                initial['related_assets'] = [asset]
            except Asset.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Article created successfully.")
        return super().form_valid(form)

class ArticleUpdateView(LoginRequiredMixin, ITStaffRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'knowledgebase/article_form.html'
    success_url = reverse_lazy('article_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Article updated successfully.")
        return super().form_valid(form)

class ArticleDeleteView(LoginRequiredMixin, ITStaffRequiredMixin, DeleteView):
    model = Article
    template_name = 'knowledgebase/article_confirm_delete.html'
    success_url = reverse_lazy('article_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Article deleted successfully.")
        return super().delete(request, *args, **kwargs)
