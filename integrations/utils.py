import requests
import logging
from django.conf import settings
from .models import WhatsAppConfig, TelegramConfig

logger = logging.getLogger(__name__)

def send_whatsapp(target_phone, message):
    """
    Sends a WhatsApp message using the configured provider (e.g., Fonnte).
    """
    try:
        config = WhatsAppConfig.load()
        if not config.is_active:
            logger.info("WhatsApp notifications are disabled.")
            return False, "WhatsApp disabled"

        if not config.api_token:
            logger.error("WhatsApp API Token is missing.")
            return False, "Missing API Token"
            
        url = config.api_url
        headers = {
            'Authorization': config.api_token,
        }
        data = {
            'target': target_phone,
            'message': message,
        }
        
        # requests might not be installed, but it is standard. 
        # If not, we might need to use urllib or ask user to install requests.
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        if response.status_code == 200:
            return True, response.text
        else:
            logger.error(f"WhatsApp API Error: {response.status_code} - {response.text}")
            return False, f"API Error: {response.status_code}"

    except Exception as e:
        logger.exception("Failed to send WhatsApp message")
        return False, str(e)


def send_telegram(target_chat_id, message):
    """
    Sends a Telegram message using the configured Bot Token.
    """
    try:
        config = TelegramConfig.load()
        if not config.is_active:
            logger.info("Telegram notifications are disabled.")
            return False, "Telegram disabled"

        if not config.bot_token:
            logger.error("Telegram Bot Token is missing.")
            return False, "Missing Bot Token"

        # If target_chat_id is not provided, try to use the default from config
        chat_id = target_chat_id or config.chat_id
        if not chat_id:
            logger.error("Telegram Chat ID is missing.")
            return False, "Missing Chat ID"

        url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown',
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            logger.error(f"Telegram API Error: {response.status_code} - {response.text}")
            return False, f"API Error: {response.status_code}"

    except Exception as e:
        logger.exception("Failed to send Telegram message")
        return False, str(e)

from django.core.mail import EmailMessage, get_connection
from .models import EmailConfig

def get_email_connection(fail_silently=False):
    """
    Returns an SMTP connection based on the stored EmailConfig.
    """
    try:
        config = EmailConfig.load()
        if not config.is_active:
            return None
        
        return get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=config.smtp_host,
            port=config.smtp_port,
            username=config.smtp_user,
            password=config.smtp_password,
            use_tls=config.use_tls,
            fail_silently=fail_silently,
        )
    except Exception as e:
        logger.error(f"Error getting email connection: {e}")
        return None

def send_email_alert(subject, message, recipient_list):
    """
    Sends an email using the dynamic SMTP configuration.
    """
    try:
        config = EmailConfig.load()
        if not config.is_active:
            logger.info("Email notifications are disabled.")
            return False, "Email disabled"

        connection = get_email_connection()
        if not connection:
            return False, "Could not establish email connection"

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=config.default_from_email,
            to=recipient_list,
            connection=connection
        )
        email.send()
        return True, "Email sent successfully"
    except Exception as e:
        logger.exception("Failed to send email alert")
        return False, str(e)
