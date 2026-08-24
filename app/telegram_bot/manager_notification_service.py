import asyncio
import html
import logging

from flask import current_app
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.extensions import db
from app.models.user import User
from app.models.wix_lead_notification import WixLeadNotification

logger = logging.getLogger(__name__)


def _format_lead_message(lead) -> str:
    order_ref = html.escape(str(lead.wix_order_number or lead.id))
    lines = [f"🆕 Нова заявка з сайту #{order_ref}", ""]
    if lead.contact_name:
        lines.append(html.escape(str(lead.contact_name)))
    if lead.contact_phone:
        lines.append(html.escape(str(lead.contact_phone)))
    lines.append("")
    if lead.item_name:
        lines.append(html.escape(str(lead.item_name)))
    if lead.amount is not None:
        amount_line = f"{lead.amount} {lead.currency or ''}".strip()
        lines.append(html.escape(amount_line))
    return "\n".join(lines)


def send_new_lead_notification(lead) -> int:
    """Notify all Telegram-linked admin/manager users about a new Wix lead.

    Returns the number of successfully sent notifications.
    """
    if not hasattr(current_app, 'telegram_bot') or not current_app.telegram_bot.is_initialized():
        logger.warning('Telegram bot not initialized, skipping new lead notification')
        return 0

    base_url = current_app.config.get('CRM_PUBLIC_URL')
    if not base_url:
        logger.warning('CRM_PUBLIC_URL not configured, skipping new lead notification')
        return 0

    recipients = User.query.filter(
        User.telegram_chat_id.isnot(None),
        User.telegram_notifications_enabled.is_(True),
        User.user_type.in_(('admin', 'manager')),
        User.is_active.is_(True),
    ).all()
    if not recipients:
        return 0

    text = _format_lead_message(lead)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            '🛒 Перейти до замовлення',
            url=f'{base_url}/orders/new?lead_id={lead.id}',
        )
    ]])

    bot = current_app.telegram_bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success_count = loop.run_until_complete(
            _send_to_all(bot, recipients, lead.id, text, keyboard)
        )
    finally:
        loop.close()
    return success_count


async def _send_to_all(bot, recipients, lead_id, text, keyboard) -> int:
    success_count = 0
    for user in recipients:
        message_id = await bot.send_message(
            chat_id=user.telegram_chat_id, text=text, reply_markup=keyboard,
        )
        if not message_id:
            continue
        db.session.add(WixLeadNotification(
            wix_lead_id=lead_id,
            user_id=user.id,
            telegram_chat_id=user.telegram_chat_id,
            telegram_message_id=message_id,
        ))
        success_count += 1
    db.session.commit()
    return success_count


def notify_lead_processed(lead) -> int:
    """Edit every sent Telegram notification for this lead to show it's processed.

    Returns the number of successfully edited messages.
    """
    if not hasattr(current_app, 'telegram_bot') or not current_app.telegram_bot.is_initialized():
        return 0

    notifications = WixLeadNotification.query.filter_by(wix_lead_id=lead.id).all()
    if not notifications:
        return 0

    base_url = current_app.config.get('CRM_PUBLIC_URL')
    if not base_url:
        return 0

    order_id = lead.processed_order_id
    url = f'{base_url}/orders/{order_id}/edit' if order_id else f'{base_url}/orders'

    processed_by = User.query.get(lead.processed_by_user_id) if lead.processed_by_user_id else None
    if processed_by:
        processed_by_name = html.escape(processed_by.display_name or processed_by.username)
    else:
        processed_by_name = 'менеджером'
    processed_at_str = lead.processed_at.strftime('%d.%m.%Y %H:%M') if lead.processed_at else ''
    suffix = f'\n\n✅ Оброблено {processed_by_name}, {processed_at_str}'.rstrip(', ')
    text = _format_lead_message(lead) + suffix
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton('✅ Оброблено — переглянути замовлення', url=url)
    ]])

    bot = current_app.telegram_bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success_count = loop.run_until_complete(_edit_all(bot, notifications, text, keyboard))
    finally:
        loop.close()
    return success_count


async def _edit_all(bot, notifications, text, keyboard) -> int:
    success_count = 0
    for notification in notifications:
        ok = await bot.edit_message(
            chat_id=notification.telegram_chat_id,
            message_id=notification.telegram_message_id,
            text=text,
            reply_markup=keyboard,
        )
        if ok:
            success_count += 1
    return success_count
