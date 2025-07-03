import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'kvitkova_crm.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Google API
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', '')
