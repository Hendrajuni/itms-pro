from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/chat/clear/', views.clear_chat, name='clear_chat'),
    path('api/chat/history/', views.chat_history, name='chat_history'),
]
