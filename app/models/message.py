from datetime import datetime

from app.extensions import db


class Message(db.Model):
    """A single inbound or outbound message in a Conversation.

    `media` is a JSON list of dicts:
        {"type": "photo", "tg_file_id": "...", "mime": "image/jpeg",
         "filename": "abc.webp", "path": "<stored filename or null>"}
    Media files are downloaded lazily (see inbox_service.ensure_media_downloaded).
    """
    __tablename__ = 'messaging_message'
    __table_args__ = (
        db.Index('ix_messaging_message_conv_extmsg', 'conversation_id', 'external_message_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey('messaging_conversation.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    direction = db.Column(db.String(4), nullable=False)  # in|out
    external_message_id = db.Column(db.String(64), nullable=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    # Outbound Telegram replies only — Instagram/Viber/WhatsApp send APIs
    # can't quote an arbitrary message.
    reply_to_message_id = db.Column(
        db.Integer, db.ForeignKey('messaging_message.id', ondelete='SET NULL'), nullable=True,
    )
    reply_to = db.relationship('Message', remote_side='Message.id', foreign_keys=[reply_to_message_id])

    text = db.Column(db.Text, nullable=True)
    media = db.Column(db.JSON, nullable=False, default=list)

    status = db.Column(db.String(12), nullable=False, default='received')  # received|sent|failed|pending|deleted|read
    # Whole current reaction set as the provider reports it, not one row per
    # reaction: [{"emoji": "\U0001f44d", "count": 1, "mine": true}]
    reactions = db.Column(db.JSON, nullable=True)
    error = db.Column(db.String(500), nullable=True)

    tg_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    conversation = db.relationship('Conversation', back_populates='messages')
    sender = db.relationship('User')

    @property
    def has_media(self):
        return bool(self.media)
