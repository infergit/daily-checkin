from datetime import datetime
import pytz
from flask import request

def get_user_timezone():
    """Get timezone from browser's cookie or default to Shanghai"""
    browser_tz = request.cookies.get('timezone', 'Asia/Shanghai')
    return pytz.timezone(browser_tz)

def to_user_timezone(utc_dt):
    """Convert UTC datetime to user's timezone"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
    return utc_dt.astimezone(get_user_timezone())