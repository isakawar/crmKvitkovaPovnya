"""
AI Agent service — LLM client, tool definitions, agent loop.
Uses OpenAI-compatible API (OpenRouter, Gemini, Anthropic, etc.)
"""
import uuid
import json
import logging
from datetime import date, datetime

import requests
from flask import current_app

from app.extensions import db
from app.models.delivery import Delivery
from app.models.client import Client
from app.models.courier import Courier
from app.models.ai_log import AIAgentLog
from app.services import delivery_service, order_service, client_service
from app.services.redis_chat_service import (
    get_history, save_history,
    save_pending_action, get_pending_action,
    claim_pending_action, delete_pending_action,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = """Ти AI асистент CRM "Kvitkova Povnya" — квіткового магазину.
Відповідай лаконічно, українською мовою.

Статуси доставок: Очікує, Доставлено, Скасовано, Розподілено.
Розміри букетів: S, M, L, XL, XXL, Власний.
Методи доставки: courier, nova_poshta.
Формат дат: YYYY-MM-DD. Формат часу: HH:MM.

ОБОВ'ЯЗКОВІ ПРАВИЛА:
1. Якщо знайдено більше одного результату — НЕ вибирай довільно.
   Покажи пронумерований список і запитай який саме потрібен.
2. Якщо не знайдено жодного результату — повідом і запропонуй уточнити.
3. Перед будь-якою зміною даних — ЗАВЖДИ виклич preview_ tool.
   Ніколи не виконуй мутацію напряму — тільки через preview.
4. Після preview поверни коротку відповідь з описом змін.
   Система сама покаже кнопки підтвердження менеджеру.
5. Сьогоднішня дата: {today}
"""

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_deliveries",
            "description": "Отримати список доставок. Фільтрація за датою та/або статусом.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "Дата від (YYYY-MM-DD). Якщо потрібна одна дата — передай в обидва поля."},
                    "date_to": {"type": "string", "description": "Дата до (YYYY-MM-DD)."},
                    "status": {"type": "string", "description": "Фільтр за статусом: Очікує, Доставлено, Скасовано"},
                    "phone": {"type": "string", "description": "Пошук за телефоном отримувача"},
                    "instagram": {"type": "string", "description": "Пошук за instagram клієнта"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_delivery",
            "description": "Знайти конкретну доставку за ID, телефоном або датою. Повертає список збігів.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delivery_id": {"type": "integer", "description": "ID доставки"},
                    "phone": {"type": "string", "description": "Телефон отримувача"},
                    "date": {"type": "string", "description": "Дата доставки (YYYY-MM-DD)"},
                    "instagram": {"type": "string", "description": "Instagram клієнта"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders",
            "description": "Отримати список замовлень з фільтрами.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Текстовий пошук"},
                    "date_from": {"type": "string", "description": "Дата від (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "Дата до (YYYY-MM-DD)"},
                    "phone": {"type": "string", "description": "Телефон"},
                    "instagram": {"type": "string", "description": "Instagram"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_clients",
            "description": "Пошук клієнтів за instagram, телефоном або telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Пошуковий запит"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_couriers",
            "description": "Отримати список активних кур'єрів.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    # --- Mutation preview tools ---
    {
        "type": "function",
        "function": {
            "name": "preview_reschedule_delivery",
            "description": "Підготувати перенесення доставки на іншу дату/час. Показує preview, не змінює дані.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delivery_id": {"type": "integer", "description": "ID доставки"},
                    "new_date": {"type": "string", "description": "Нова дата (YYYY-MM-DD)"},
                    "new_time_from": {"type": "string", "description": "Новий час від (HH:MM), необов'язково"},
                    "new_time_to": {"type": "string", "description": "Новий час до (HH:MM), необов'язково"},
                    "ai_message": {"type": "string", "description": "Оригінальний запит користувача"}
                },
                "required": ["delivery_id", "new_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_update_delivery",
            "description": "Підготувати зміну полів доставки (коментар, адреса, побажання). Preview, без збереження.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delivery_id": {"type": "integer"},
                    "comment": {"type": "string"},
                    "preferences": {"type": "string"},
                    "street": {"type": "string"},
                    "address_comment": {"type": "string"},
                    "ai_message": {"type": "string"}
                },
                "required": ["delivery_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_set_delivery_status",
            "description": "Підготувати зміну статусу доставки. Preview, без збереження.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delivery_id": {"type": "integer"},
                    "new_status": {"type": "string", "description": "Очікує | Доставлено | Скасовано"},
                    "ai_message": {"type": "string"}
                },
                "required": ["delivery_id", "new_status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_assign_courier",
            "description": "Підготувати призначення кур'єра на доставки. Preview, без збереження.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delivery_ids": {"type": "array", "items": {"type": "integer"}},
                    "courier_id": {"type": "integer"},
                    "ai_message": {"type": "string"}
                },
                "required": ["delivery_ids", "courier_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_create_client",
            "description": "Підготувати створення нового клієнта. Preview, без збереження.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instagram": {"type": "string"},
                    "phone": {"type": "string"},
                    "telegram": {"type": "string"},
                    "ai_message": {"type": "string"}
                },
                "required": ["instagram"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_create_order",
            "description": "Підготувати створення нового замовлення для клієнта. Preview, без збереження. Розміри: S, M, L, XL, XXL, Власний.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID клієнта (отримай через search_clients)"},
                    "recipient_name": {"type": "string", "description": "Ім'я отримувача"},
                    "recipient_phone": {"type": "string", "description": "Телефон отримувача"},
                    "delivery_date": {"type": "string", "description": "Дата доставки YYYY-MM-DD"},
                    "size": {"type": "string", "description": "S | M | L | XL | XXL | Власний"},
                    "street": {"type": "string", "description": "Вулиця і будинок"},
                    "city": {"type": "string", "description": "Місто, за замовчуванням Київ"},
                    "time_from": {"type": "string", "description": "Час від HH:MM"},
                    "time_to": {"type": "string", "description": "Час до HH:MM"},
                    "comment": {"type": "string"},
                    "is_pickup": {"type": "boolean", "description": "Самовивіз"},
                    "ai_message": {"type": "string"}
                },
                "required": ["client_id", "recipient_name", "recipient_phone", "delivery_date", "size"]
            }
        }
    },
]


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def _call_llm(messages: list, with_tools: bool = True) -> dict:
    api_key = current_app.config['AI_API_KEY']
    base_url = current_app.config['AI_BASE_URL'].rstrip('/')
    model = current_app.config['AI_MODEL']

    system = SYSTEM_PROMPT.format(today=date.today().strftime('%d.%m.%Y'))
    # Sanitize messages: Gemini rejects null content
    clean_messages = []
    for m in messages:
        m = dict(m)
        if m.get('content') is None:
            m['content'] = ''
        clean_messages.append(m)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + clean_messages,
    }
    if with_tools:
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"

    response = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

def _tool_get_deliveries(args: dict) -> str:
    deliveries, _, _ = delivery_service.get_deliveries(
        date_from_str=args.get('date_from'),
        date_to_str=args.get('date_to'),
        recipient_phone=args.get('phone'),
        client_instagram=args.get('instagram'),
        status=args.get('status'),
    )
    if not deliveries:
        return "Доставок не знайдено."
    lines = [f"Знайдено {len(deliveries)} доставок:"]
    for d in deliveries[:30]:  # limit to avoid huge context
        courier_name = d.courier.name if d.courier else 'не призначено'
        client_info = d.client.instagram if d.client else '—'
        lines.append(
            f"#{d.id} | {d.delivery_date} | {d.time_from or '?'}–{d.time_to or '?'} | "
            f"{d.phone or '—'} | {d.street or 'самовивіз'} | "
            f"Статус: {d.status} | Кур'єр: {courier_name} | Клієнт: {client_info}"
        )
    if len(deliveries) > 30:
        lines.append(f"... і ще {len(deliveries) - 30}. Уточніть фільтр.")
    return "\n".join(lines)


def _tool_find_delivery(args: dict) -> str:
    results = []
    if args.get('delivery_id'):
        d = Delivery.query.get(args['delivery_id'])
        if d:
            results = [d]
    else:
        q = Delivery.query
        if args.get('phone'):
            q = q.filter(Delivery.phone.contains(args['phone']))
        if args.get('date'):
            try:
                dt = datetime.strptime(args['date'], '%Y-%m-%d').date()
                q = q.filter(Delivery.delivery_date == dt)
            except ValueError:
                pass
        if args.get('instagram'):
            q = q.join(Client).filter(Client.instagram.contains(args['instagram']))
        results = q.order_by(Delivery.delivery_date.desc()).limit(10).all()

    if not results:
        return "Доставок не знайдено. Перевір параметри пошуку."
    if len(results) == 1:
        d = results[0]
        courier_name = d.courier.name if d.courier else 'не призначено'
        client_info = d.client.instagram if d.client else '—'
        return (
            f"Знайдено 1 доставку:\n"
            f"#{d.id} | Дата: {d.delivery_date} | Час: {d.time_from or '?'}–{d.time_to or '?'}\n"
            f"Телефон: {d.phone or '—'} | Адреса: {d.street or 'самовивіз'}\n"
            f"Статус: {d.status} | Кур'єр: {courier_name} | Клієнт: {client_info}\n"
            f"Коментар: {d.comment or '—'}"
        )
    # multiple — list them, do NOT choose
    lines = [f"Знайдено {len(results)} доставок. Уточни яку саме:"]
    for i, d in enumerate(results, 1):
        lines.append(
            f"{i}. #{d.id} | {d.delivery_date} {d.time_from or '?'}–{d.time_to or '?'} | "
            f"{d.phone or '—'} | {d.street or 'самовивіз'} | {d.status}"
        )
    return "\n".join(lines)


def _tool_get_orders(args: dict) -> str:
    orders = order_service.get_orders(
        q=args.get('query'),
        phone=args.get('phone'),
        instagram=args.get('instagram'),
        date_from=args.get('date_from'),
        date_to=args.get('date_to'),
    )
    if not orders:
        return "Замовлень не знайдено."
    lines = [f"Знайдено {len(orders)} замовлень:"]
    for o in orders[:20]:
        lines.append(
            f"#{o.id} | {o.delivery_date} | {o.recipient_name or '—'} | "
            f"{o.recipient_phone or '—'} | Розмір: {o.size} | Клієнт: {o.client.instagram if o.client else '—'}"
        )
    if len(orders) > 20:
        lines.append(f"... і ще {len(orders) - 20}. Уточніть пошук.")
    return "\n".join(lines)


def _tool_search_clients(args: dict) -> str:
    pagination = client_service.search_clients(q=args.get('query', ''), per_page=15)
    clients = pagination.items
    if not clients:
        return "Клієнтів не знайдено."
    lines = [f"Знайдено {len(clients)} клієнтів:"]
    for c in clients[:15]:
        lines.append(
            f"#{c.id} | @{c.instagram} | {c.phone or '—'} | "
            f"Telegram: {c.telegram or '—'} | Кредити: {c.credits or 0}"
        )
    return "\n".join(lines)


def _tool_get_couriers(_args: dict) -> str:
    couriers = Courier.query.filter_by(active=True).all()
    if not couriers:
        return "Активних кур'єрів немає."
    lines = [f"Активних кур'єрів: {len(couriers)}"]
    for c in couriers:
        lines.append(f"#{c.id} | {c.name} | {c.phone or '—'}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mutation preview tools
# ---------------------------------------------------------------------------

def _delivery_to_dict(d: Delivery) -> dict:
    return {
        'id': d.id,
        'delivery_date': str(d.delivery_date),
        'time_from': d.time_from,
        'time_to': d.time_to,
        'street': d.street,
        'phone': d.phone,
        'status': d.status,
        'comment': d.comment,
        'preferences': d.preferences,
        'courier_id': d.courier_id,
        'courier_name': d.courier.name if d.courier else None,
        'address_comment': d.address_comment,
    }


def _tool_preview_reschedule_delivery(args: dict, user_id: int) -> str:
    d = Delivery.query.get(args['delivery_id'])
    if not d:
        return f"Помилка: доставку #{args['delivery_id']} не знайдено."
    if d.status == 'Доставлено':
        return "Помилка: доставка вже виконана, перенесення неможливе."

    try:
        new_date = datetime.strptime(args['new_date'], '%Y-%m-%d').date()
    except ValueError:
        return f"Помилка: невірний формат дати '{args['new_date']}'. Використовуй YYYY-MM-DD."

    if new_date < date.today():
        return f"Помилка: дата {args['new_date']} вже в минулому."

    before = _delivery_to_dict(d)
    action_id = str(uuid.uuid4())[:8]

    client_info = d.client.instagram if d.client else '—'
    old_time = f"{d.time_from or '?'}–{d.time_to or '?'}"
    new_time_from = args.get('new_time_from') or d.time_from
    new_time_to = args.get('new_time_to') or d.time_to
    new_time = f"{new_time_from or '?'}–{new_time_to or '?'}"

    action = {
        'type': 'reschedule_delivery',
        'delivery_id': d.id,
        'new_date': args['new_date'],
        'new_time_from': new_time_from,
        'new_time_to': new_time_to,
        'before': before,
        'ai_message': args.get('ai_message', ''),
        'preview_text': (
            f"Доставка #{d.id}\n"
            f"Клієнт: {client_info} | Тел: {d.phone or '—'}\n"
            f"Зараз: {d.delivery_date}, {old_time}\n"
            f"Нова дата: {args['new_date']}, {new_time}"
        )
    }
    save_pending_action(user_id, action_id, action)
    return f"[PENDING:{action_id}]"


def _tool_preview_update_delivery(args: dict, user_id: int) -> str:
    d = Delivery.query.get(args['delivery_id'])
    if not d:
        return f"Помилка: доставку #{args['delivery_id']} не знайдено."

    before = _delivery_to_dict(d)
    action_id = str(uuid.uuid4())[:8]
    fields = {k: v for k, v in args.items() if k not in ('delivery_id', 'ai_message') and v is not None}

    changes = []
    for field, new_val in fields.items():
        old_val = getattr(d, field, '—') or '—'
        changes.append(f"  {field}: {old_val} → {new_val}")

    action = {
        'type': 'update_delivery',
        'delivery_id': d.id,
        'fields': fields,
        'before': before,
        'ai_message': args.get('ai_message', ''),
        'preview_text': (
            f"Зміна доставки #{d.id}\n"
            + "\n".join(changes)
        )
    }
    save_pending_action(user_id, action_id, action)
    return f"[PENDING:{action_id}]"


def _tool_preview_set_delivery_status(args: dict, user_id: int) -> str:
    valid_statuses = ['Очікує', 'Доставлено', 'Скасовано', 'Розподілено']
    if args['new_status'] not in valid_statuses:
        return f"Помилка: невірний статус '{args['new_status']}'. Допустимі: {', '.join(valid_statuses)}"

    d = Delivery.query.get(args['delivery_id'])
    if not d:
        return f"Помилка: доставку #{args['delivery_id']} не знайдено."

    before = _delivery_to_dict(d)
    action_id = str(uuid.uuid4())[:8]
    client_info = d.client.instagram if d.client else '—'

    action = {
        'type': 'set_delivery_status',
        'delivery_id': d.id,
        'new_status': args['new_status'],
        'before': before,
        'ai_message': args.get('ai_message', ''),
        'preview_text': (
            f"Зміна статусу доставки #{d.id}\n"
            f"Клієнт: {client_info} | {d.delivery_date}\n"
            f"Поточний статус: {d.status} → {args['new_status']}"
        )
    }
    save_pending_action(user_id, action_id, action)
    return f"[PENDING:{action_id}]"


def _tool_preview_assign_courier(args: dict, user_id: int) -> str:
    courier = Courier.query.filter_by(id=args['courier_id'], active=True).first()
    if not courier:
        return f"Помилка: кур'єра #{args['courier_id']} не знайдено або він неактивний."

    deliveries = Delivery.query.filter(Delivery.id.in_(args['delivery_ids'])).all()
    if not deliveries:
        return "Помилка: жодної доставки не знайдено."

    action_id = str(uuid.uuid4())[:8]
    lines = [f"Призначення кур'єра {courier.name} на {len(deliveries)} доставок:"]
    for d in deliveries:
        lines.append(f"  #{d.id} | {d.delivery_date} | {d.phone or '—'}")

    action = {
        'type': 'assign_courier',
        'delivery_ids': [d.id for d in deliveries],
        'courier_id': courier.id,
        'before': {str(d.id): {'courier_id': d.courier_id, 'status': d.status} for d in deliveries},
        'ai_message': args.get('ai_message', ''),
        'preview_text': "\n".join(lines)
    }
    save_pending_action(user_id, action_id, action)
    return f"[PENDING:{action_id}]"


def _tool_preview_create_client(args: dict, user_id: int) -> str:
    existing = Client.query.filter_by(instagram=args['instagram']).first()
    if existing:
        return f"Помилка: клієнт з instagram @{args['instagram']} вже існує (#{existing.id})."

    if args.get('phone'):
        existing_phone = Client.query.filter_by(phone=args['phone']).first()
        if existing_phone:
            return f"Помилка: клієнт з телефоном {args['phone']} вже існує (#{existing_phone.id})."

    action_id = str(uuid.uuid4())[:8]
    action = {
        'type': 'create_client',
        'instagram': args['instagram'],
        'phone': args.get('phone'),
        'telegram': args.get('telegram'),
        'ai_message': args.get('ai_message', ''),
        'preview_text': (
            f"Створення нового клієнта:\n"
            f"Instagram: @{args['instagram']}\n"
            f"Телефон: {args.get('phone') or '—'}\n"
            f"Telegram: {args.get('telegram') or '—'}"
        )
    }
    save_pending_action(user_id, action_id, action)
    return f"[PENDING:{action_id}]"


def _tool_preview_create_order(args: dict, user_id: int) -> str:
    client = Client.query.get(args['client_id'])
    if not client:
        return f"Помилка: клієнта #{args['client_id']} не знайдено."
    try:
        datetime.strptime(args['delivery_date'], '%Y-%m-%d')
    except ValueError:
        return f"Помилка: невірний формат дати '{args['delivery_date']}'."
    valid_sizes = ['S', 'M', 'L', 'XL', 'XXL', 'Власний']
    if args['size'] not in valid_sizes:
        return f"Помилка: невірний розмір '{args['size']}'. Допустимі: {', '.join(valid_sizes)}"

    action_id = str(uuid.uuid4())[:8]
    is_pickup = args.get('is_pickup', False)
    action = {
        'type': 'create_order',
        'client_id': args['client_id'],
        'recipient_name': args['recipient_name'],
        'recipient_phone': args['recipient_phone'],
        'delivery_date': args['delivery_date'],
        'size': args['size'],
        'street': args.get('street', ''),
        'city': args.get('city', 'Київ'),
        'time_from': args.get('time_from'),
        'time_to': args.get('time_to'),
        'comment': args.get('comment'),
        'is_pickup': is_pickup,
        'ai_message': args.get('ai_message', ''),
        'preview_text': (
            f"Нове замовлення\n"
            f"Клієнт: @{client.instagram}\n"
            f"Отримувач: {args['recipient_name']} | {args['recipient_phone']}\n"
            f"Дата: {args['delivery_date']}"
            + (f" {args.get('time_from','')}–{args.get('time_to','')}" if args.get('time_from') else "") + "\n"
            f"Розмір: {args['size']} | {'Самовивіз' if is_pickup else args.get('street','—')}\n"
            f"Місто: {args.get('city','Київ')}"
        )
    }
    save_pending_action(user_id, action_id, action)
    return f"[PENDING:{action_id}]"


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def _execute_tool(tool_name: str, args: dict, user_id: int) -> str:
    try:
        if tool_name == 'get_deliveries':
            return _tool_get_deliveries(args)
        elif tool_name == 'find_delivery':
            return _tool_find_delivery(args)
        elif tool_name == 'get_orders':
            return _tool_get_orders(args)
        elif tool_name == 'search_clients':
            return _tool_search_clients(args)
        elif tool_name == 'get_couriers':
            return _tool_get_couriers(args)
        elif tool_name == 'preview_reschedule_delivery':
            return _tool_preview_reschedule_delivery(args, user_id)
        elif tool_name == 'preview_update_delivery':
            return _tool_preview_update_delivery(args, user_id)
        elif tool_name == 'preview_set_delivery_status':
            return _tool_preview_set_delivery_status(args, user_id)
        elif tool_name == 'preview_assign_courier':
            return _tool_preview_assign_courier(args, user_id)
        elif tool_name == 'preview_create_client':
            return _tool_preview_create_client(args, user_id)
        elif tool_name == 'preview_create_order':
            return _tool_preview_create_order(args, user_id)
        else:
            return f"Помилка: невідомий tool '{tool_name}'"
    except Exception as e:
        logger.exception(f"Tool {tool_name} failed: {e}")
        return f"Помилка виконання {tool_name}: {str(e)}"


# ---------------------------------------------------------------------------
# Validation before execute
# ---------------------------------------------------------------------------

def validate_before_execute(action: dict) -> list:
    errors = []
    action_type = action.get('type')

    if action_type == 'reschedule_delivery':
        d = Delivery.query.get(action.get('delivery_id'))
        if not d:
            errors.append(f"Доставку #{action.get('delivery_id')} не знайдено")
        else:
            if d.status == 'Доставлено':
                errors.append("Доставка вже виконана, перенесення неможливе")
            try:
                new_date = datetime.strptime(action['new_date'], '%Y-%m-%d').date()
                if new_date < date.today():
                    errors.append(f"Дата {action['new_date']} вже в минулому")
            except (ValueError, KeyError):
                errors.append("Невірний формат дати")

    elif action_type == 'update_delivery':
        d = Delivery.query.get(action.get('delivery_id'))
        if not d:
            errors.append(f"Доставку #{action.get('delivery_id')} не знайдено")

    elif action_type == 'set_delivery_status':
        d = Delivery.query.get(action.get('delivery_id'))
        if not d:
            errors.append(f"Доставку #{action.get('delivery_id')} не знайдено")
        valid = ['Очікує', 'Доставлено', 'Скасовано', 'Розподілено']
        if action.get('new_status') not in valid:
            errors.append(f"Невірний статус: {action.get('new_status')}")

    elif action_type == 'assign_courier':
        courier = Courier.query.filter_by(id=action.get('courier_id'), active=True).first()
        if not courier:
            errors.append(f"Кур'єра #{action.get('courier_id')} не знайдено або неактивний")
        for d_id in (action.get('delivery_ids') or []):
            d = Delivery.query.get(d_id)
            if not d:
                errors.append(f"Доставку #{d_id} не знайдено")

    elif action_type == 'create_client':
        if Client.query.filter_by(instagram=action.get('instagram')).first():
            errors.append(f"Клієнт з instagram @{action.get('instagram')} вже існує")

    return errors


# ---------------------------------------------------------------------------
# Execute confirmed action
# ---------------------------------------------------------------------------

def execute_confirmed_action(action: dict, user_id: int) -> tuple[bool, str, dict | None]:
    """
    Execute a confirmed mutation.
    Returns (success, reply_text, after_data)
    """
    action_type = action.get('type')

    try:
        if action_type == 'reschedule_delivery':
            d = Delivery.query.get(action['delivery_id'])
            data = {'delivery_date': action['new_date']}
            if action.get('new_time_from'):
                data['time_from'] = action['new_time_from']
            if action.get('new_time_to'):
                data['time_to'] = action['new_time_to']
            delivery_service.update_delivery(d, data)
            after = _delivery_to_dict(d)
            reply = (
                f"Готово! Доставку #{d.id} перенесено на {action['new_date']}"
                + (f" {action.get('new_time_from', '')}–{action.get('new_time_to', '')}" if action.get('new_time_from') else "")
            )
            return True, reply, after

        elif action_type == 'update_delivery':
            d = Delivery.query.get(action['delivery_id'])
            delivery_service.update_delivery(d, action['fields'])
            after = _delivery_to_dict(d)
            return True, f"Готово! Доставку #{d.id} оновлено.", after

        elif action_type == 'set_delivery_status':
            d = Delivery.query.get(action['delivery_id'])
            delivery_service.set_delivery_status(d, action['new_status'])
            after = _delivery_to_dict(d)
            return True, f"Готово! Статус доставки #{d.id} змінено на '{action['new_status']}'.", after

        elif action_type == 'assign_courier':
            courier = Courier.query.get(action['courier_id'])
            ok, err = delivery_service.assign_courier_to_deliveries(
                action['delivery_ids'], action['courier_id']
            )
            if not ok:
                return False, f"Помилка: {err}", None
            after = {str(d_id): {'courier_id': action['courier_id']} for d_id in action['delivery_ids']}
            return True, f"Готово! Кур'єра {courier.name} призначено на {len(action['delivery_ids'])} доставок.", after

        elif action_type == 'create_client':
            client, error = client_service.create_client(
                instagram=action['instagram'],
                phone=action.get('phone'),
                telegram=action.get('telegram'),
            )
            if error:
                return False, f"Помилка: {error.get('message', str(error))}", None
            after = {'id': client.id, 'instagram': client.instagram}
            return True, f"Готово! Клієнта @{client.instagram} створено (#{client.id}).", after

        elif action_type == 'create_order':
            client = Client.query.get(action['client_id'])
            if not client:
                return False, f"Клієнта #{action['client_id']} не знайдено.", None
            form = {
                'recipient_name': action['recipient_name'],
                'recipient_phone': action['recipient_phone'],
                'first_delivery_date': action['delivery_date'],
                'size': action['size'],
                'city': action.get('city', 'Київ'),
                'street': action.get('street', ''),
                'is_pickup': 'on' if action.get('is_pickup') else '',
                'time_from': action.get('time_from') or '',
                'time_to': action.get('time_to') or '',
                'comment': action.get('comment') or '',
                'delivery_method': 'courier',
                'for_whom': '',
            }
            order = order_service.create_order_and_deliveries(client, form)
            after = {'order_id': order.id}
            return True, (
                f"Готово! Замовлення #{order.id} створено.\n"
                f"Клієнт: @{client.instagram} | Отримувач: {action['recipient_name']}\n"
                f"Дата: {action['delivery_date']} | Розмір: {action['size']}"
            ), after

        else:
            return False, f"Невідомий тип дії: {action_type}", None

    except Exception as e:
        logger.exception(f"execute_confirmed_action failed: {e}")
        return False, f"Помилка виконання: {str(e)}", None


def write_audit_log(user_id: int, action: dict, status: str,
                    after_data: dict = None, error_msg: str = None) -> None:
    try:
        entity_type_map = {
            'reschedule_delivery': 'delivery',
            'update_delivery': 'delivery',
            'set_delivery_status': 'delivery',
            'assign_courier': 'delivery',
            'create_client': 'client',
        }
        action_type = action.get('type', '')
        entity_id = (
            action.get('delivery_id') or
            action.get('delivery_ids', [None])[0] if action.get('delivery_ids') else None
        )
        log = AIAgentLog(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type_map.get(action_type),
            entity_id=entity_id,
            before_data=action.get('before'),
            after_data=after_data,
            ai_message=action.get('ai_message', ''),
            status=status,
            error_msg=error_msg,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")
        db.session.rollback()


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

def run_agent_turn(user_message: str, user_id: int) -> dict:
    """
    Process one user message. Returns { reply, pending_action }.
    pending_action is set when a mutation preview was prepared.
    """
    history = get_history(user_id)
    history.append({"role": "user", "content": user_message})

    pending_action = None

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = _call_llm(history)
        except requests.HTTPError as e:
            body = ''
            try:
                body = e.response.json()
            except Exception:
                pass
            logger.error(f"LLM HTTP error: {e} | body: {body}")
            status = getattr(e.response, 'status_code', '')
            if status == 404:
                return {"reply": f"Модель не знайдена ({current_app.config['AI_MODEL']}). Перевір AI_MODEL в .env.", "pending_action": None}
            if status == 401:
                return {"reply": "Невірний AI_API_KEY. Перевір .env.", "pending_action": None}
            if status == 429:
                return {"reply": "Ліміт запитів вичерпано (безкоштовна модель). Зачекай 1-2 хвилини і спробуй ще раз.", "pending_action": None}
            return {"reply": f"Помилка AI ({status}). Спробуй ще раз.", "pending_action": None}
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return {"reply": f"Помилка AI: {str(e)}", "pending_action": None}

        choice = response['choices'][0]
        msg = choice['message']

        # Add assistant message to history — ensure content is never null (Gemini requirement)
        if msg.get('content') is None:
            msg['content'] = ''
        history.append(msg)

        if choice.get('finish_reason') == 'tool_calls' or msg.get('tool_calls'):
            tool_calls = msg.get('tool_calls', [])
            tool_results = []

            for tc in tool_calls:
                tool_name = tc['function']['name']
                try:
                    args = json.loads(tc['function']['arguments'])
                except json.JSONDecodeError:
                    args = {}

                result = _execute_tool(tool_name, args, user_id)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "content": result,
                })

                # Check if any tool returned a pending action
                if result.startswith('[PENDING:'):
                    action_id = result[9:-1]
                    pending_action = get_pending_action(user_id, action_id)
                    if pending_action:
                        pending_action['action_id'] = action_id

            history.extend(tool_results)
            continue  # next iteration — let LLM process tool results

        # No more tool calls — final answer
        reply = msg.get('content', '')
        save_history(user_id, history)
        return {"reply": reply, "pending_action": pending_action}

    # Reached max iterations
    save_history(user_id, history)
    return {"reply": "Не вдалося завершити дію. Спробуй уточнити запит.", "pending_action": pending_action}
