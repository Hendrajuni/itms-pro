from integrations.utils import send_telegram

def send_telegram_message(message):
    """
    Wrapper for integrations.utils.send_telegram to maintain compatibility
    with existing signals, using the default configured chat_id.
    """
    # send_telegram(target_chat_id, message)
    # Passing None as target_chat_id will fallback to the default chat_id in config
    send_telegram(None, message)
