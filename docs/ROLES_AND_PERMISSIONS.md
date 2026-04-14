# Ролі та права доступу — CRM Kvitkova Povnya

## Ролі користувачів

| Роль | `user_type` | Опис |
|------|------------|------|
| **admin** | `admin` | Повний доступ. Управління користувачами CRM. |
| **manager** | `manager` | Доступ до всього функціоналу крім управління користувачами. |
| **florist** | `florist` | Доступ лише до сторінки `/florist`. |
| courier | `courier` | Доступ тільки через Telegram бот (не через web). |

---

## Матриця доступу

| Сторінка / Функція | admin | manager | florist |
|--------------------|-------|---------|---------|
| Dashboard `/dashboard` | ✓ | ✓ | ✗ |
| Клієнти `/clients` | ✓ | ✓ | ✗ |
| Замовлення `/orders` | ✓ | ✓ | ✗ |
| Підписки `/subscriptions` | ✓ | ✓ | ✗ |
| Маршрути `/routes`, `/route-generator` | ✓ | ✓ | ✗ |
| Сертифікати `/certificates` | ✓ | ✓ | ✗ |
| Транзакції `/transactions` | ✓ | ✓ | ✗ |
| Флорист `/florist` | ✓ | ✓ | ✓ |
| Звіти `/reports` | ✓ | ✗ | ✗ |
| Налаштування `/settings` | ✓ | ✓ | ✗ |
| Управління користувачами (в Settings) | ✓ | ✗ | ✗ |
| AI Асистент (чат) | ✓ | ✓ | ✗ |

---

## Permissions (права доступу)

Визначені в `app/models/user.py` у словнику `ROLE_PERMISSIONS`:

### admin
```
view_orders, edit_orders, delete_orders
view_clients, edit_clients, delete_clients
view_couriers, edit_couriers, delete_couriers
view_deliveries, edit_deliveries, delete_deliveries
view_distribution, edit_distribution
view_reports
view_settings, edit_settings
manage_users
```

### manager
```
view_orders, edit_orders, delete_orders
view_clients, edit_clients, delete_clients
view_couriers, edit_couriers, delete_couriers
view_deliveries, edit_deliveries, delete_deliveries
view_distribution, edit_distribution
view_settings, edit_settings
```

---

## Де перевіряються права

### Декоратор `@permission_required`
Файл: `app/utils/decorators.py`

Використовується на окремих маршрутах:
```python
@bp.route('/settings')
@login_required
@permission_required('view_settings')
def settings_page(): ...
```

### Глобальний `before_request` (`app/__init__.py`)
- Перевіряє, що всі користувачі авторизовані (крім `auth.login` та `static`)
- Florist users жорстко обмежені: можуть заходити тільки на `/florist` та `/auth` маршрути, всі інші → redirect

### Шаблони (Jinja2)
Умовний рендер елементів sidebar і секцій:
```html
{% if current_user.has_permission('view_reports') %}
  <a href="/reports">Звіти</a>
{% endif %}

{% if current_user.has_permission('manage_users') %}
  {# секція управління користувачами #}
{% endif %}
```

---

## Управління користувачами

### Головний admin-акаунт
Створюється автоматично при деплої через:
```bash
flask ensure-admin
```
Параметри беруться з `.env`:
- `ADMIN_USERNAME` (default: `admin`)
- `ADMIN_EMAIL` (default: `admin@kvitkovapovnya.com`)
- `ADMIN_PASSWORD` (обов'язковий)

### Управління через UI (тільки для admin)

Розташування: **Налаштування → секція "Користувачі CRM"**

Доступні дії:
- **Створити** нового менеджера або флориста (логін, email, роль, пароль × 2)
- **Деактивувати / Активувати** — блокує логін (поле `is_active = False`)
- **Змінити пароль** — вводиться двічі для підтвердження

### API endpoints (AJAX, тільки admin)

| Метод | URL | Дія |
|-------|-----|-----|
| GET | `/settings/users` | Список всіх users (крім поточного admin) |
| POST | `/settings/users` | Створити user (JSON: username, email, role, password, password_confirm) |
| POST | `/settings/users/<id>/toggle-active` | Перемикнути is_active |
| POST | `/settings/users/<id>/password` | Змінити пароль (JSON: password, password_confirm) |

---

## Як додати нову роль

1. Додати константу в `app/models/user.py`:
   ```python
   ROLE_NEW = 'new_role'
   ```
2. Додати permissions у `ROLE_PERMISSIONS`:
   ```python
   ROLE_NEW: ['view_orders', ...]
   ```
3. Якщо потрібні специфічні обмеження (як у florist) — додати перевірку в `before_request` у `app/__init__.py`
4. Оновити матрицю та UI: sidebar в `app/templates/layout.html`, список ролей у `app/blueprints/settings/routes.py` (endpoint `/settings/users` POST, поле `role`)
5. Додати роль у select в шаблоні `app/templates/settings/index.html` (modal `#userCreateModal`)

## Як додати новий permission

1. Додати рядок у `ROLE_PERMISSIONS[ROLE_NAME]` в `app/models/user.py`
2. Захистити маршрут:
   ```python
   @permission_required('new_permission')
   ```
3. При потребі: сховати елемент в шаблоні через `{% if current_user.has_permission('new_permission') %}`
