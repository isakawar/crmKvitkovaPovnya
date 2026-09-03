from datetime import datetime

from app.extensions import db


class MessagingChannelAccess(db.Model):
    """Which managers can see/answer an inbox channel."""
    __tablename__ = 'messaging_channel_access'
    __table_args__ = (
        db.UniqueConstraint('channel_id', 'user_id', name='uq_messaging_channel_access'),
    )

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer, db.ForeignKey('messaging_channel.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    channel = db.relationship('MessagingChannel', back_populates='access_entries')
    user = db.relationship('User')
