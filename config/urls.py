"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('portal-admin/', admin.site.urls),
    path('tickets/', include('tickets.urls')),
    path('assets/', include('assets.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('governance/', include('governance.urls')),
    path('network/', include('network.urls')),
    path('knowledge/', include('knowledgebase.urls')),
    path('notifications/', include('notifications.urls')),
    path('integrations/', include('integrations.urls')),
    path('administration/', include('administration.urls')),
    path('', include('core.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
