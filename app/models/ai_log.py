from datetime import datetime
from app.extensions import db


class AIAgentLog(db.Model):
    __tablename__ = 'ai_agent_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50))   # reschedule_delivery, update_order, etc.
    entity_type = db.Column(db.String(50))   # delivery, order, client
    entity_id = db.Column(db.Integer)
    before_data = db.Column(db.JSON)
    after_data = db.Column(db.JSON)
    ai_message = db.Column(db.Text)          # original user request
    status = db.Column(db.String(20))        # executed, cancelled, failed, validation_error
    error_msg = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('ai_logs', lazy=True))

    def __repr__(self):
        return f'<AIAgentLog {self.action_type} {self.entity_type}#{self.entity_id} {self.status}>'
