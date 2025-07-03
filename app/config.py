import os

class DevelopmentConfig:
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, '..', 'instance', 'kvitkova_crm.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
