from app import create_app
from flask_migrate import Migrate
from app.extensions import db

app = create_app()

with app.app_context():
    from alembic import command
    from alembic.config import Config
    
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message="Initial migration with updated order model") 