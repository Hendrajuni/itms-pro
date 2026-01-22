from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, DetailView, CreateView, UpdateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, F
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from .models import Article, Category
from .forms import ArticleForm

class KnowledgeHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'knowledge/knowledge_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Search Logic
        query = self.request.GET.get('q')
        if query:
            context['search_results'] = Article.objects.filter(
                Q(title__icontains=query) | Q(content__icontains=query),
                status='Published'
            )
            context['query'] = query
        else:
            # Categories with Article Counts
            context['categories'] = Category.objects.annotate(
                article_count=Count('articles', filter=Q(articles__status='Published'))
            ).filter(article_count__gt=0)
            
            # Trending (Popular)
            context['popular_articles'] = Article.objects.filter(
                status='Published'
            ).order_by('-view_count')[:5]
            
            # Recent
            context['recent_articles'] = Article.objects.filter(
                status='Published'
            ).order_by('-created_at')[:5]
            
        return context

class ArticleDetailView(LoginRequiredMixin, DetailView):
    model = Article
    template_name = 'knowledge/article_detail.html'
    context_object_name = 'article'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Increment View Count efficiently
        Article.objects.filter(pk=obj.pk).update(view_count=F('view_count') + 1)
        obj.refresh_from_db()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Related Articles (Same Category, exclude current)
        if self.object.category:
            context['related_articles'] = Article.objects.filter(
                category=self.object.category,
                status='Published'
            ).exclude(pk=self.object.pk)[:5]
        return context

# --- Staff Only Views ---

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.groups.filter(name='Manager').exists()

class ArticleCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'knowledge/article_form.html'
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)
        
    def get_success_url(self):
        return reverse('article_detail', kwargs={'pk': self.object.pk})

class ArticleUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'knowledge/article_form.html'
    
    def get_success_url(self):
        return reverse('article_detail', kwargs={'pk': self.object.pk})
