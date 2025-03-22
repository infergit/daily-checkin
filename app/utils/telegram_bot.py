import telebot
import logging
from flask import current_app

logger = logging.getLogger(__name__)

def configure_telegram_bot(app):
    """Configure the Telegram bot with handlers"""
    bot_token = app.config.get('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.warning("Telegram bot token not configured")
        return None
        
    bot = telebot.TeleBot(bot_token)
    
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        """Handle /start command - respond with chat ID"""
        chat_id = message.chat.id
        bot.reply_to(message, 
            f"Welcome to Daily Check-in Bot!\n\n"
            f"Your Chat ID is: <code>{chat_id}</code>\n\n"
            f"Copy this ID and paste it in your settings page to receive check-in notifications."
        )
        
    @bot.message_handler(commands=['help'])
    def send_help(message):
        """Handle /help command"""
        bot.reply_to(message,
            "This bot sends you notifications when your friends complete their daily check-ins.\n\n"
            "Available commands:\n"
            "/start - Get your Chat ID\n"
            "/help - Show this help message"
        )
    
    return bot