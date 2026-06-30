from datetime import datetime
from app.extensions import db


class ActionItem(db.Model):
    __tablename__ = "action_item"

    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    due_at          = db.Column(db.DateTime)
    completion_mode = db.Column(db.String(20), nullable=False, default="all")  # "any" | "all"
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by      = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    creator    = db.relationship("User", foreign_keys=[created_by], lazy="joined")
    recipients = db.relationship(
        "ActionItemRecipient",
        back_populates="action_item",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class ActionItemRecipient(db.Model):
    __tablename__ = "action_item_recipient"

    id             = db.Column(db.Integer, primary_key=True)
    action_item_id = db.Column(
        db.Integer,
        db.ForeignKey("action_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id        = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status         = db.Column(db.String(20), nullable=False, default="pending", index=True)
    completed_at   = db.Column(db.DateTime)

    action_item = db.relationship("ActionItem", back_populates="recipients")
    user        = db.relationship("User", foreign_keys=[user_id], lazy="joined")
