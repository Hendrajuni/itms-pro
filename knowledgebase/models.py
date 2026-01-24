from django.db import models
from django.conf import settings
from ckeditor.fields import RichTextField
from django.utils.text import slugify

class Article(models.Model):
    CATEGORY_CHOICES = [
        ('TROUBLESHOOTING', 'Troubleshooting'),
        ('TUTORIAL', 'Tutorial / How-To'),
        ('SOP', 'SOP / Procedure'),
        ('GENERAL', 'General Info'),
        ('SCRIPT', 'Scripts & Configs'),
    ]

    VISIBILITY_CHOICES = [
        ('PUBLIC', 'Public (All Staff)'),
        ('INTERNAL', 'Internal (IT Only)'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='GENERAL')
    
    content = RichTextField(help_text="Write your article here. Use Code Snippet for scripts.")
    
    # Relationships
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='articles')
    related_assets = models.ManyToManyField('assets.Asset', blank=True, related_name='kb_articles', help_text="Link to specific assets (e.g. Server X)")
    
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='PUBLIC')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    views_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure unique slug
            original_slug = self.slug
            count = 1
            while Article.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{count}"
                count += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title}"
