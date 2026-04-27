import os
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://kvitkova_user:kvitkova_password@localhost:5432/kvitkova_crm'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Bot settings
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    
    # Login configuration
    LOGIN_DISABLED = False
    REMEMBER_COOKIE_DURATION = 86400  # 24 hours in seconds
    ROUTE_OPTIMIZER_URL = os.environ.get('ROUTE_OPTIMIZER_URL', '')
    DEPOT_ADDRESS = os.environ.get('DEPOT_ADDRESS', '')
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

    # AI Agent
    AI_API_KEY = os.environ.get('AI_API_KEY', '')
    AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://openrouter.ai/api/v1')
    AI_MODEL = os.environ.get('AI_MODEL', 'qwen/qwen3-235b-a22b:free')
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Photo uploads
    UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'uploads', 'order_photos')
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB
    ALLOWED_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'heic'}

class DevelopmentConfig:
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = 'postgresql://kvitkova_user:kvitkova_password@localhost:5432/kvitkova_crm'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Bot настройки
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_WEBHOOK_URL = os.environ.get('TELEGRAM_WEBHOOK_URL', '')
    TELEGRAM_WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', 'webhook_secret')
    TELEGRAM_NOTIFICATIONS_ENABLED = os.environ.get('TELEGRAM_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
    ROUTE_OPTIMIZER_URL = os.environ.get('ROUTE_OPTIMIZER_URL', '')
    DEPOT_ADDRESS = os.environ.get('DEPOT_ADDRESS', '')
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

    # AI Agent
    AI_API_KEY = os.environ.get('AI_API_KEY', '')
    AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://openrouter.ai/api/v1')
    AI_MODEL = os.environ.get('AI_MODEL', 'qwen/qwen3-235b-a22b:free')
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Photo uploads
    UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'uploads', 'order_photos')
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB
    ALLOWED_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'heic'}

class ProductionConfig(DevelopmentConfig):
    DEBUG = False
    # Тут можна додати URI для продакшн БД

class TestingConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}
