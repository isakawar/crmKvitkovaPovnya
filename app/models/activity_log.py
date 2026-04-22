from datetime import datetime
from app.extensions import db


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    user_label  = db.Column(db.String(100))
    action      = db.Column(db.String(20))
    entity_type = db.Column(db.String(30))
    entity_id   = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(255))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', lazy='joined', passive_deletes=True)
