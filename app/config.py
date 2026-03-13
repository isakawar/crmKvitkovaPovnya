import os
from dotenv import load_dotenv

load_dotenv()

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
    ROUTE_OPTIMIZER_URL = os.environ.get('ROUTE_OPTIMIZER_URL', 'http://34.55.114.149:3000')
    DEPOT_ADDRESS = os.environ.get('DEPOT_ADDRESS', '')

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
    ROUTE_OPTIMIZER_URL = os.environ.get('ROUTE_OPTIMIZER_URL', 'http://34.55.114.149:3000')
    DEPOT_ADDRESS = os.environ.get('DEPOT_ADDRESS', '')

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
