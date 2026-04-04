from flask import Blueprint

ai_agent_bp = Blueprint('ai_agent', __name__)

from app.blueprints.ai_agent import routes  # noqa
