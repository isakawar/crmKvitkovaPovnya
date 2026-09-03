from datetime import datetime

from app.extensions import db


class MessagingChannel(db.Model):
    """A configured corporate messaging account (Telegram, later Instagram/Viber/WhatsApp).

    Secrets (bot token) live in env, not here. `external_id` holds the
    Telegram Business `business_connection_id` once the owner connects the bot.
    """
    __tablename__ = 'messaging_channel'

    id = db.Column(db.Integer, primary_key=True)
    channel_type = db.Column(db.String(20), nullable=False, default='telegram')  # telegram|instagram|viber|whatsapp
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    external_id = db.Column(db.String(128), nullable=True)  # telegram business_connection_id
    webhook_secret = db.Column(db.String(64), nullable=False)
    config = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    access_entries = db.relationship(
        'MessagingChannelAccess', back_populates='channel',
        cascade='all, delete-orphan', lazy='selectin',
    )
    conversations = db.relationship('Conversation', back_populates='channel', lazy='dynamic')

    @property
    def is_connected(self):
        return bool(self.external_id)

    @property
    def manager_ids(self):
        return {a.user_id for a in self.access_entries}
