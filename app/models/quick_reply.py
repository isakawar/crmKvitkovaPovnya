from datetime import datetime

from app.extensions import db


class QuickReply(db.Model):
    """A canned response text any manager can insert into the inbox composer.

    Shared across the team (like the rest of /inbox), not per-user — a small
    shop's managers reuse each other's phrasing rather than keeping private
    lists.
    """
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    author = db.relationship('User')
