from django.urls import path
from . import views

urlpatterns = [
    path('', views.KnowledgeHomeView.as_view(), name='knowledge_home'),
    path('article/create/', views.ArticleCreateView.as_view(), name='article_create'),
    path('article/<int:pk>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('article/<int:pk>/edit/', views.ArticleUpdateView.as_view(), name='article_update'),
]
