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

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey('messaging_conversation.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    direction = db.Column(db.String(4), nullable=False)  # in|out
    external_message_id = db.Column(db.String(64), nullable=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    text = db.Column(db.Text, nullable=True)
    media = db.Column(db.JSON, nullable=False, default=list)

    status = db.Column(db.String(12), nullable=False, default='received')  # received|sent|failed|pending|deleted
    error = db.Column(db.String(500), nullable=True)

    tg_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    conversation = db.relationship('Conversation', back_populates='messages')
    sender = db.relationship('User')

    @property
    def has_media(self):
        return bool(self.media)
