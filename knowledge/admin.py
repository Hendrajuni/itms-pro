from django.contrib import admin
from .models import Category, Article

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'status', 'updated_at', 'view_count')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'content')
    autocomplete_fields = ['category', 'author']
    autocomplete_fields = ['category', 'author']
    readonly_fields = ('view_count', 'created_at', 'updated_at')
    filter_horizontal = ('related_assets',)


    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)
