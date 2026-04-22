from app.extensions import db
from app.models.activity_log import ActivityLog


def log(user, action: str, entity_type: str, entity_id: int | None, description: str) -> None:
    entry = ActivityLog(
        user_id=user.id if user else None,
        user_label=(user.display_name or user.username) if user else '—',
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
    )
    db.session.add(entry)
    db.session.commit()
