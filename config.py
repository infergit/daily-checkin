# config.py
import os
from datetime import timedelta

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-should-be-changed'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Telegram bot configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', '')
    
    # AWS S3 configuration
    AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY', '')
    AWS_SECRET_KEY = os.environ.get('AWS_SECRET_KEY', '')
    AWS_REGION = os.environ.get('AWS_REGION', '')
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
    
    # AWS CloudFront configuration
    USE_CLOUDFRONT = os.environ.get('USE_CLOUDFRONT', 'False').lower() in ('true', '1', 't', 'yes')
    CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', '')
    CLOUDFRONT_KEY_PAIR_ID = os.environ.get('CLOUDFRONT_KEY_PAIR_ID', '')
    CLOUDFRONT_PRIVATE_KEY_PATH = os.environ.get('CLOUDFRONT_PRIVATE_KEY_PATH', '')
    
    # Image processing configuration
    MAX_IMAGE_SIZE = int(os.environ.get('MAX_IMAGE_SIZE', 5 * 1024 * 1024))  # 5MB default
    ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif']  # Add iPhone formats
    THUMBNAIL_SIZE = (300, 300)  # Default thumbnail dimensions
    
    # Backup configuration
    AUTO_BACKUP_ENABLED = os.environ.get('AUTO_BACKUP_ENABLED', 'True').lower() in ('true', '1', 't')
    BACKUP_COUNT = int(os.environ.get('BACKUP_COUNT', 5))
    
    # Miscellaneous
    TIMEZONE_DEFAULT = os.environ.get('TIMEZONE_DEFAULT', 'UTC')
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 10))
    
    # Redis configuration for URL caching
    REDIS_HOST = os.environ.get('REDIS_HOST')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_SSL = os.environ.get('REDIS_SSL', 'False').lower() == 'true'
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_URL = os.environ.get('REDIS_URL')

class DevelopmentConfig(Config):
    # Development-specific settings
    # You can override Redis settings for development if needed
    pass

class ProductionConfig(Config):
    # Production-specific settings
    pass

