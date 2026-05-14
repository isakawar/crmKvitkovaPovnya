from app.extensions import db
from app.models.activity_log import ActivityLog


def log(user, action: str, entity_type: str, entity_id: int | None, description: str,
        before_data: dict | None = None, after_data: dict | None = None) -> None:
    entry = ActivityLog(
        user_id=user.id if user else None,
        user_label=(user.display_name or user.username) if user else '—',
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        before_data=before_data,
        after_data=after_data,
    )
    db.session.add(entry)
