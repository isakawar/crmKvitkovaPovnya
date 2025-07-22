import sys
import os

# Додаємо корінь проєкту до Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from flask_migrate import Migrate
from app.extensions import db

app = create_app()

with app.app_context():
    from alembic import command
    from alembic.config import Config
    
    alembic_cfg = Config("../config/alembic.ini")
    alembic_cfg.set_main_option("script_location", "migrations")
    command.revision(alembic_cfg, autogenerate=True, message="Initial migration with updated order model") 