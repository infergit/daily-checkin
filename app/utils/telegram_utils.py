import requests
import logging
import threading
from flask import current_app
from app.models.models import FriendRelationship, User
from app.utils.timezone import to_user_timezone

logger = logging.getLogger(__name__)

def send_telegram_message(chat_id, message, disable_notification=False):
    """
    Send a message to a specific Telegram chat
    
    Args:
        chat_id: The Telegram chat ID to send to
        message: The message text
        disable_notification: Whether to send silently (no notification)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            logger.error("Telegram bot token not configured")
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_notification": disable_notification
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            logger.info(f"Message sent to chat_id '{chat_id}' successfully")
            return True
        else:
            logger.error(f"Failed to send message: {response.text}")
            return False
            
    except Exception as e:
        logger.exception(f"Error sending Telegram message: {str(e)}")
        return False

def send_async_telegram_message(chat_id, message, disable_notification=False):
    """Send a Telegram message asynchronously in a background thread"""
    from flask import current_app
    app = current_app._get_current_object()  # Get the actual app object, not the proxy
    
    def send_with_context():
        with app.app_context():
            send_telegram_message(chat_id, message, disable_notification)
    
    thread = threading.Thread(target=send_with_context)
    thread.daemon = True
    thread.start()
    return True

def format_checkin_notification(sender_username, project_name, check_note, check_time):
    """Format a check-in notification message"""
    # Format the time in a user-friendly way
    local_time = to_user_timezone(check_time)
    formatted_time = local_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Create the message
    message = (
        f"🔔 <b>Check-in Alert!</b>\n\n"
        f"Your friend <b>{sender_username}</b> just completed a check-in "
        f"for project <b>{project_name}</b>!\n\n"
    )
    
    # Add check-in note if provided
    if check_note and check_note.strip():
        message += f"📝 <b>Note:</b> \"{check_note}\"\n\n"
    
    # Add check-in time
    message += f"⏰ <b>Time:</b> {formatted_time}"
    
    return message

def notify_friends_of_checkin(user, project, checkin):
    """
    Notify all eligible friends when a user completes a check-in
    
    Args:
        user: The user who completed the check-in
        project: The project checked into
        checkin: The check-in record
    """
    # Find all accepted friend relationships for this user
    friend_relationships = FriendRelationship.query.filter(
        ((FriendRelationship.requester_id == user.id) | 
         (FriendRelationship.addressee_id == user.id)),
        FriendRelationship.status == 'accepted'
    ).all()
    
    # Get all friend IDs
    friend_ids = []
    for rel in friend_relationships:
        if rel.requester_id == user.id:
            friend_ids.append(rel.addressee_id)
        else:
            friend_ids.append(rel.requester_id)
    
    # Find friends who want notifications and have a valid Telegram chat ID
    notification_sent = 0
    for friend_id in friend_ids:
        try:
            friend = User.query.get(friend_id)
            if not friend:
                continue
                
            # Check if friend wants notifications and has Telegram set up
            if not friend.wants_checkin_notifications() or not friend.has_valid_telegram():
                continue
                
            # Get friend's Telegram chat ID
            chat_id = friend.get_preference('telegram_chat_id')
            if not chat_id:
                continue
                
            # Format and send the notification
            message = format_checkin_notification(
                user.username,
                project.name,
                checkin.note,
                checkin.check_time
            )
            
            send_async_telegram_message(chat_id, message)
            logger.info(f"Notification sent to user {friend.id} for check-in {checkin.id}")
            notification_sent += 1
            
        except Exception as e:
            # Log error but continue with other friends
            logger.exception(f"Error sending notification to friend {friend_id}: {str(e)}")
            continue
    
    logger.info(f"Total {notification_sent} notifications sent for check-in {checkin.id}")
    return True