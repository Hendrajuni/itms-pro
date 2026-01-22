from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse
from .models import WhatsAppConfig, TelegramConfig, EmailConfig
from .forms import WhatsAppForm, TelegramForm, EmailConfigForm
from .utils import send_whatsapp, send_telegram, send_email_alert

class NotificationSettingsView(LoginRequiredMixin, View):
    template_name = 'integrations/settings.html'

    def get(self, request):
        whatsapp_config = WhatsAppConfig.load()
        telegram_config = TelegramConfig.load()
        email_config = EmailConfig.load()
        
        whatsapp_form = WhatsAppForm(instance=whatsapp_config, prefix='whatsapp')
        telegram_form = TelegramForm(instance=telegram_config, prefix='telegram')
        email_form = EmailConfigForm(instance=email_config, prefix='email')
        
        context = {
            'whatsapp_form': whatsapp_form,
            'telegram_form': telegram_form,
            'email_form': email_form,
            'page_title': 'Notification Gateway Settings'
        }
        return render(request, self.template_name, context)

    def post(self, request):
        whatsapp_config = WhatsAppConfig.load()
        telegram_config = TelegramConfig.load()
        email_config = EmailConfig.load()
        
        whatsapp_form = WhatsAppForm(request.POST, instance=whatsapp_config, prefix='whatsapp')
        telegram_form = TelegramForm(request.POST, instance=telegram_config, prefix='telegram')
        email_form = EmailConfigForm(request.POST, instance=email_config, prefix='email')
        
        if 'submit_whatsapp' in request.POST:
            if whatsapp_form.is_valid():
                whatsapp_form.save()
                messages.success(request, "WhatsApp settings updated successfully.")
                return redirect('integrations:settings')
        
        if 'submit_telegram' in request.POST:
            if telegram_form.is_valid():
                telegram_form.save()
                messages.success(request, "Telegram settings updated successfully.")
                return redirect('integrations:settings')

        if 'submit_email' in request.POST:
            if email_form.is_valid():
                email_form.save()
                messages.success(request, "Email settings updated successfully.")
                return redirect('integrations:settings')

        context = {
            'whatsapp_form': whatsapp_form,
            'telegram_form': telegram_form,
            'email_form': email_form,
            'page_title': 'Notification Gateway Settings'
        }
        return render(request, self.template_name, context)

class TestNotificationView(LoginRequiredMixin, View):
    def post(self, request):
        provider = request.POST.get('provider')
        target = request.POST.get('target')
        
        if not target:
            return JsonResponse({'success': False, 'message': 'Target is required.'})

        message = "This is a test notification from the System."
        
        if provider == 'whatsapp':
            success, result = send_whatsapp(target, message)
        elif provider == 'telegram':
            success, result = send_telegram(target, message)
        elif provider == 'email':
            success, result = send_email_alert("Test Notification", message, [target])
        else:
            return JsonResponse({'success': False, 'message': 'Invalid provider.'})
            
        if success:
            return JsonResponse({'success': True, 'message': f'Test message sent successfully! Response: {result}'})
        else:
            return JsonResponse({'success': False, 'message': f'Failed to send message. Error: {result}'})
