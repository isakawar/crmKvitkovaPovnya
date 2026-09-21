from datetime import datetime

from app.extensions import db


class Conversation(db.Model):
    """One dialog with a contact on a messaging channel.

    Channel-agnostic. `client_id` links to a CRM Client — set automatically
    on first contact when `client_service.find_client_for_contact` finds an
    unambiguous match (by Instagram/Telegram handle or phone, gated by the
    client's `phone_viber`/`phone_telegram`/`phone_whatsapp` flags), or by a
    manager by hand via `inbox_service.link_client`. Stays null otherwise —
    never guessed between multiple candidates.
    """
    __tablename__ = 'messaging_conversation'
    __table_args__ = (
        db.UniqueConstraint('channel_id', 'external_chat_id', name='uq_conversation_channel_chat'),
    )

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer, db.ForeignKey('messaging_channel.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    external_chat_id = db.Column(db.String(64), nullable=False)

    contact_name = db.Column(db.String(255), nullable=True)
    contact_username = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(32), nullable=True)

    client_id = db.Column(db.Integer, db.ForeignKey('client.id', ondelete='SET NULL'), nullable=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    status = db.Column(db.String(12), nullable=False, default='open')  # open|closed

    last_message_at = db.Column(db.DateTime, nullable=True, index=True)
    last_message_preview = db.Column(db.String(200), nullable=True)
    last_message_direction = db.Column(db.String(4), nullable=True)  # in|out
    unread_count = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    channel = db.relationship('MessagingChannel', back_populates='conversations')
    client = db.relationship('Client')
    assigned_user = db.relationship('User')
    messages = db.relationship(
        'Message', back_populates='conversation',
        cascade='all, delete-orphan', order_by='Message.id',
        lazy='dynamic',
    )

    @property
    def display_name(self):
        return (self.contact_name
                or (f'@{self.contact_username}' if self.contact_username else None)
                or self.contact_phone
                or f'#{self.external_chat_id}')
