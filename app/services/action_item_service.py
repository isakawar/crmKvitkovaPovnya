from datetime import datetime
from app.extensions import db
from app.models.action_item import ActionItem, ActionItemRecipient


def get_pending_for_user(user_id: int) -> list:
    now = datetime.utcnow()
    rows = (
        ActionItemRecipient.query
        .join(ActionItem, ActionItemRecipient.action_item_id == ActionItem.id)
        .filter(
            ActionItemRecipient.user_id == user_id,
            ActionItemRecipient.status == 'pending',
        )
        .order_by(
            (ActionItem.due_at < now).desc(),
            ActionItem.due_at.asc().nullslast(),
            ActionItem.created_at.asc(),
        )
        .all()
    )
    return rows


def get_pending_count_for_user(user_id: int) -> int:
    return (
        ActionItemRecipient.query
        .filter(
            ActionItemRecipient.user_id == user_id,
            ActionItemRecipient.status == 'pending',
        )
        .count()
    )


def create_action_item(admin_user, title: str, description: str, due_at, completion_mode: str, user_ids: list) -> ActionItem:
    item = ActionItem(
        title=title,
        description=description or None,
        due_at=due_at,
        completion_mode=completion_mode,
        created_by=admin_user.id,
    )
    db.session.add(item)
    db.session.flush()

    for uid in user_ids:
        recipient = ActionItemRecipient(action_item_id=item.id, user_id=uid)
        db.session.add(recipient)

    db.session.commit()
    return item


def complete_action_item(item_id: int, manager_user) -> tuple:
    recipient = ActionItemRecipient.query.filter_by(
        action_item_id=item_id,
        user_id=manager_user.id,
        status='pending',
    ).first()

    if not recipient:
        return False, 'Завдання не знайдено або вже виконано'

    now = datetime.utcnow()

    if recipient.action_item.completion_mode == 'any':
        # Mark all recipients as done
        (
            ActionItemRecipient.query
            .filter_by(action_item_id=item_id, status='pending')
            .update({'status': 'done', 'completed_at': now}, synchronize_session=False)
        )
    else:
        recipient.status = 'done'
        recipient.completed_at = now

    db.session.commit()
    return True, ''


def list_all_for_admin() -> list:
    return (
        ActionItem.query
        .order_by(ActionItem.created_at.desc())
        .all()
    )


def delete_action_item(item_id: int) -> None:
    item = ActionItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()


