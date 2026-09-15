from datetime import datetime

from app.extensions import db


class MessagingChannel(db.Model):
    """A configured corporate messaging account (Telegram, later Instagram/Viber/WhatsApp).

    Secrets (bot token) live in env, not here. `external_id` holds the
    Telegram Business `business_connection_id` once the owner connects the bot.
    """
    __tablename__ = 'messaging_channel'

    id = db.Column(db.Integer, primary_key=True)
    channel_type = db.Column(db.String(20), nullable=False, default='telegram')  # telegram|telegram_personal|instagram|viber|whatsapp
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    external_id = db.Column(db.String(128), nullable=True)  # telegram business_connection_id / telegram_personal own user id
    webhook_secret = db.Column(db.String(64), nullable=False)
    config = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # telegram_personal (MTProto/Telethon) — session strings are encrypted (Fernet),
    # see app/services/messaging/session_crypto.py. Never read/write these raw.
    phone_number = db.Column(db.String(32), nullable=True)
    session_encrypted = db.Column(db.Text, nullable=True)
    pending_session_encrypted = db.Column(db.Text, nullable=True)
    pending_phone_code_hash = db.Column(db.String(128), nullable=True)

    # instagram (Facebook Login for Business OAuth) — the Facebook Page this IG
    # Business account is linked to, and its Page Access Token (also valid for
    # sending/receiving IG messages), encrypted the same way as session_encrypted.
    # external_id holds the IG-scoped account id (from the OAuth page picker).
    fb_page_id = db.Column(db.String(64), nullable=True)
    fb_page_access_token_encrypted = db.Column(db.Text, nullable=True)

    # whatsapp (Facebook Login for Business — Embedded Signup) — the WhatsApp
    # Business Account id and its access token, encrypted the same way.
    # external_id holds the phone_number_id (used in the send URL).
    wa_waba_id = db.Column(db.String(64), nullable=True)
    wa_access_token_encrypted = db.Column(db.Text, nullable=True)

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
