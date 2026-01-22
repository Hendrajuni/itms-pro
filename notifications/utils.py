import requests
from .models import TelegramConfig

def send_telegram_message(message):
    """
    Sends a message to the active Telegram group.
    """
    try:
        config = TelegramConfig.objects.filter(is_active=True).first()
        if not config:
            # print("No active Telegram Config found.")
            return

        url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
        payload = {
            'chat_id': config.alert_chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=payload, timeout=5)
        if response.status_code != 200:
            print(f"Failed to send Telegram message: {response.text}")
            
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
