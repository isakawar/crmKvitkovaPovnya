# AI Agent Chat Widget — Implementation Plan

> **Живий документ.** Відмічай `[x]` коли крок виконано. Якщо контекст скинувся — прочитай цей файл і продовжуй з першого незавершеного кроку.

---

## Загальна ідея

Floating chat-кнопка в правому нижньому куті CRM. Відкриває панель чату з AI агентом, який:
- Відповідає на питання по БД (доставки, замовлення, клієнти)
- Виконує мутації (перенесення, редагування, створення) — **завжди з підтвердженням через preview-картку**
- Зберігає історію в Redis (TTL 3 дні)
- Доступний тільки для ролей `admin` і `manager`

---

## Стек доповнень

- **LLM:** будь-який OpenAI-compatible провайдер (OpenRouter / Gemini / Anthropic) — налаштовується через `.env`
- **Tool calling:** OpenAI-compatible format (`tools` + `tool_choice: auto`)
- **History:** Redis (`redis-py`), ключ `ai_chat_history:{user_id}`, TTL 259200 сек
- **Pending actions:** Redis, ключ `ai_pending:{user_id}:{action_id}`, TTL 600 сек
- **Audit:** нова таблиця `ai_agent_log` у PostgreSQL

---

## Нові файли

```
app/blueprints/ai_agent/__init__.py
app/blueprints/ai_agent/routes.py
app/services/ai_agent_service.py
app/services/redis_chat_service.py
app/models/ai_log.py
migrations/versions/XXXX_add_ai_agent_log.py
```

---

## Змінені файли

```
app/config.py              — нові змінні: AI_API_KEY, AI_BASE_URL, AI_MODEL, REDIS_URL
.env                       — секрети для LLM провайдера і Redis
app/__init__.py            — реєстрація ai_agent_bp
app/templates/layout.html  — floating button + chat panel
requirements.txt           — додати: redis
```

---

## PHASE 1 — Інфраструктура

### Крок 1.1 — Залежності та конфіг
- [x] Додати `redis` до `requirements.txt`
- [x] Додати до `app/config.py`:
  ```python
  AI_API_KEY = os.environ.get('AI_API_KEY', '')
  AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://openrouter.ai/api/v1')
  AI_MODEL = os.environ.get('AI_MODEL', 'qwen/qwen3-235b-a22b:free')
  REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
  ```
- [ ] Додати змінні в `.env` (фактичні ключі):
  ```
  AI_API_KEY=...
  AI_BASE_URL=https://openrouter.ai/api/v1
  AI_MODEL=qwen/qwen3-235b-a22b:free
  REDIS_URL=redis://localhost:6379/0
  ```

### Крок 1.2 — Redis service
- [ ] Створити `app/services/redis_chat_service.py` з функціями:
  - `get_history(user_id)` → list of messages
  - `save_history(user_id, messages)` → setex 3 дні (259200 сек)
  - `save_pending_action(user_id, action_id, action)` → setex 10 хв, `status: "pending"`
  - `get_pending_action(user_id, action_id)` → dict або None
  - `claim_pending_action(user_id, action_id)` → атомарно міняє status на "executing" через Redis pipeline WATCH/MULTI/EXEC, повертає False якщо вже не "pending" (idempotency — захист від подвійного кліку)
  - `delete_pending_action(user_id, action_id)` → видалити ключ

### Крок 1.3 — Audit Log міграція
- [ ] Створити міграцію `migrations/versions/XXXX_add_ai_agent_log.py`:
  ```sql
  CREATE TABLE ai_agent_log (
      id          SERIAL PRIMARY KEY,
      user_id     INTEGER REFERENCES "user"(id),
      action_type VARCHAR(50),    -- reschedule_delivery, update_order, create_client...
      entity_type VARCHAR(50),    -- delivery, order, client
      entity_id   INTEGER,
      before_data JSONB,          -- стан до змін
      after_data  JSONB,          -- стан після змін
      ai_message  TEXT,           -- оригінальний запит менеджера
      status      VARCHAR(20),    -- executed, cancelled, failed, validation_error
      error_msg   TEXT,
      created_at  TIMESTAMP DEFAULT NOW()
  );
  ```
- [ ] Створити модель `app/models/ai_log.py` (клас `AIAgentLog`)
- [ ] Додати імпорт моделі в `app/__init__.py`
- [ ] Запустити `flask db upgrade`

---

## PHASE 2 — AI Service та Tools

### Крок 2.1 — Базовий LLM клієнт
- [x] Створити `app/services/ai_agent_service.py`
- [x] Функція `call_llm(messages, tools=None)` → POST до `{AI_BASE_URL}/chat/completions`
  - headers: `Authorization: Bearer {AI_API_KEY}`
  - timeout: 30 сек
  - повертає розпарсений JSON або кидає `LLMError`
- [x] System prompt як константа:
  ```
  Ти AI асистент CRM "Kvitkova Povnya" — квіткового магазину.
  Відповідай лаконічно, українською.
  Статуси доставок: Очікує, Доставлено, Скасовано.
  Розміри: S, M, L, XL, XXL, Власний.

  ПРАВИЛА:
  - Якщо знайдено >1 результат — НЕ вибирай довільно. Покажи список і запитай який саме.
  - Якщо знайдено 0 результатів — повідом і запропонуй уточнити.
  - Перед будь-якою зміною даних — виклич preview tool. Ніколи не виконуй мутацію без preview.
  ```

### Крок 2.2 — Read Tools (без підтвердження)
- [ ] `get_deliveries(date_from, date_to, status=None)` → `delivery_service.get_deliveries()`
  - Повертає список: id, client name/phone, address, time, status, courier
- [ ] `find_delivery(delivery_id=None, phone=None, date=None)` → пошук конкретної доставки
  - Якщо >1 результат → повертає список з полем `multiple: true`
- [ ] `get_orders(query=None, date_from=None, date_to=None)` → `order_service.get_orders()`
- [ ] `search_clients(query)` → `client_service.search_clients()`
- [ ] `get_couriers()` → `Courier.query.filter_by(active=True).all()`

### Крок 2.3 — Mutation Preview Tools (не виконують, тільки готують preview)
Кожен mutation tool:
1. Знаходить запис і перевіряє існування
2. Формує `before_data` (поточний стан)
3. Формує `after_data` (що зміниться)
4. Зберігає в Redis як pending_action із `uuid` як action_id
5. Повертає human-readable preview + action_id

- [ ] `preview_reschedule_delivery(delivery_id, new_date, new_time_from, new_time_to)`
  - Перевірки: delivery існує, не "Доставлено", нова дата не в минулому
  - Preview: "Доставка #42 | Іріна • 0666... | 04.04 10:00–12:00 → 05.04 14:00–15:00"
- [ ] `preview_update_delivery(delivery_id, fields)` — змінити коментар, адресу, florist_status
- [ ] `preview_set_delivery_status(delivery_id, new_status)`
  - Перевірка: статус є у списку допустимих
- [ ] `preview_assign_courier(delivery_ids, courier_id)`
  - Перевірка: кур'єр активний, доставки існують
- [ ] `preview_update_order(order_id, fields)`
- [ ] `preview_create_client(instagram, phone, telegram=None)`
  - Перевірка: дублікат по instagram/phone
- [ ] `preview_create_order(client_id, delivery_date, size, address, ...)`

### Крок 2.4 — Tool dispatch та agent loop
- [x] `execute_tool(tool_name, arguments, user_id)` → router по всіх tools
- [x] `run_agent_turn(user_message, user_id)` → головна функція:
  1. Завантажити history з Redis
  2. Додати user message
  3. `call_llm(messages, tools=ALL_TOOLS)`
  4. Якщо є `tool_calls` → `execute_tool()` для кожного → додати `tool` messages → ще раз `call_llm` (loop до max 5 ітерацій)
  5. Зберегти оновлену history в Redis
  6. Повернути `{ reply, pending_action }` (pending_action якщо є preview)

---

## PHASE 3 — Backend Endpoints

### Крок 3.1 — Blueprint
- [x] Створити `app/blueprints/ai_agent/__init__.py`
- [ ] Створити `app/blueprints/ai_agent/routes.py` з `ai_agent_bp = Blueprint('ai_agent', __name__)`
- [x] Зареєструвати в `app/__init__.py`

### Крок 3.2 — POST /ai/chat
- [ ] Перевірити роль: тільки `admin` / `manager` → інакше 403
- [ ] Отримати `message` з JSON body
- [ ] Викликати `run_agent_turn(message, current_user.id)`
- [ ] Повернути `{ reply, pending_action }`

### Крок 3.3 — POST /ai/confirm
- [ ] Отримати `{ action_id, confirmed: true/false }` з JSON body
- [ ] `claim_pending_action(user_id, action_id)` — якщо False → 409 "Дію вже виконано"
- [ ] Якщо `confirmed=false` → записати в audit log (status=cancelled) → повернути "Скасовано"
- [ ] `validate_before_execute(action)` → якщо є помилки → audit log (validation_error) → повернути помилки
- [ ] Виконати реальну мутацію
- [ ] Записати в `ai_agent_log` (status=executed, before_data, after_data)
- [ ] Видалити pending_action з Redis
- [ ] Повернути `{ success: true, reply: "Готово! Доставку #42 перенесено..." }`

### Крок 3.4 — GET /ai/history
- [x] Повернути останні 50 повідомлень для відображення при відкритті панелі
- [x] Захист: login_required + роль

### Крок 3.5 — Validation before execute
- [ ] `validate_before_execute(action)` → повертає `list[str]` помилок:
  - reschedule: delivery існує, не "Доставлено", дата не в минулому
  - update: запис існує
  - create_order: client існує, розмір валідний
  - assign_courier: кур'єр активний, доставки не "Доставлено"

---

## PHASE 4 — Frontend

### Крок 4.1 — Floating button
- [x] В `layout.html` перед `</body>`, в умові `current_user.role.name in ['admin', 'manager']`:
  - Кнопка: `fixed bottom-6 right-6 z-50 w-14 h-14 bg-amber-500 hover:bg-amber-600 rounded-full shadow-lg`
  - Іконка: `bi bi-robot text-xl`

### Крок 4.2 — Chat Panel HTML
- [ ] Панель: `fixed bottom-24 right-6 z-50 w-80 bg-white rounded-2xl shadow-2xl border border-stone-200`, висота 480px, прихована (`hidden`)
- [ ] Header: "AI Асистент" + кнопка [×]
- [ ] Messages area: `overflow-y-auto flex flex-col gap-2 p-3`
- [ ] Typing indicator (прихований за замовчуванням)
- [ ] Input: `textarea` (1-3 рядки) + кнопка Send

### Крок 4.3 — Message Bubbles
- [x] User bubble: `bg-amber-100 rounded-2xl rounded-br-sm self-end max-w-[85%] px-3 py-2 text-sm`
- [x] AI bubble: `bg-stone-100 rounded-2xl rounded-bl-sm self-start max-w-[85%] px-3 py-2 text-sm`
- [ ] Функція `appendMessage(role, text)` → додає bubble в DOM + scroll to bottom

### Крок 4.4 — Confirmation Card
- [ ] Якщо `response.pending_action != null` → рендерити картку:
  ```
  ┌──────────────────────────────────┐
  │ Підтвердження змін               │
  │                                  │
  │  [preview текст з pending_action] │
  │                                  │
  │  [✓ Підтвердити]  [✗ Скасувати]  │
  └──────────────────────────────────┘
  ```
  Стиль: `border border-amber-300 bg-amber-50 rounded-xl p-3 text-sm`
- [ ] [Підтвердити] → `POST /ai/confirm { action_id, confirmed: true }` → прибрати картку, показати reply
- [ ] [Скасувати] → `POST /ai/confirm { action_id, confirmed: false }` → прибрати картку

### Крок 4.5 — JS логіка
- [ ] `openChat()` → показати панель + `GET /ai/history` → рендерити повідомлення
- [ ] `sendMessage()`:
  1. Взяти текст, очистити textarea
  2. `appendMessage('user', text)` + показати typing indicator + заблокувати input
  3. `fetch('/ai/chat', { method: 'POST', body: JSON.stringify({message: text}) })`
  4. Сховати typing indicator + розблокувати input
  5. `appendMessage('ai', response.reply)`
  6. Якщо `response.pending_action` → рендерити confirmation card
- [x] Enter (без Shift) → надіслати

---

## PHASE 5 — Тестування

### Крок 5.1 — Ручне тестування
- [ ] Read query: "Скільки доставок на сьогодні?" → відповідь з числом
- [ ] Ambiguity: запит де є 2+ результати → AI питає уточнення, НЕ виконує дію
- [ ] Reschedule happy path: знайти → preview карточка → підтвердити → перевірити в БД
- [ ] Reschedule cancel: preview → скасувати → дані НЕ змінились в БД
- [ ] Double confirm: підтвердити двічі швидко → другий раз отримати 409 / "вже виконано"
- [ ] Validation: дата в минулому → помилка валідації, мутація не виконана
- [ ] Florist login → кнопка НЕ видима
- [ ] Перезавантажити сторінку → відкрити чат → history збереглась (Redis)

### Крок 5.2 — Перевірка audit log
- [ ] Після успішної мутації → запис у `ai_agent_log` з before/after
- [ ] Після скасування → `status=cancelled`
- [ ] Після validation error → `status=validation_error`

### Крок 5.3 — Регресія
- [ ] `pytest` → всі існуючі тести проходять

---

## Важливі деталі (для відновлення контексту)

**Таблиці БД (реальні назви):**
`order`, `delivery`, `client`, `courier`, `user` (не `orders`, `users` і т.д.)

**Статуси доставок:** `Очікує`, `Доставлено`, `Скасовано`

**Ролі:** `admin`, `manager`, `florist`, `courier`

**Існуючі сервіси (імпорти):**
```python
from app.services.delivery_service import get_deliveries, update_delivery, set_delivery_status, assign_courier_to_deliveries
from app.services.order_service import get_orders, update_order, create_order_and_deliveries
from app.services.client_service import search_clients, create_client, get_client_by_id
from app.models.courier import Courier
from app.models.delivery import Delivery
from app.models.order import Order
```

**Сигнатури сервісів:**
- `get_deliveries(date_from_str, date_to_str, client_instagram=None, recipient_phone=None, financial_week=None, status=None)`
- `update_delivery(delivery_obj, data_dict)` — data_dict з полями які змінюємо
- `set_delivery_status(delivery_obj, new_status_str)`
- `assign_courier_to_deliveries(delivery_ids_list, courier_id)`
- `get_orders(q=None, phone=None, instagram=None, city=None, size=None, delivery_type=None, date_from=None, date_to=None)`
- `search_clients(q, sub_filter=None, page=1, per_page=20)`
- `create_client(instagram, phone, telegram=None, credits=0, marketing_source=None, personal_discount=0)`

**Toast у JS:** `showToast('text', 'success'|'error')`

**AJAX pattern:**
```javascript
const resp = await fetch('/path', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
});
const result = await resp.json();
```

**Blueprint pattern** (`app/__init__.py` рядки 36-63):
```python
from app.blueprints.ai_agent.routes import ai_agent_bp
app.register_blueprint(ai_agent_bp)
```

**layout.html:** sidebar займає 64px (`ml-16` на main content). Floating button: `fixed` позиція, `z-50`.
