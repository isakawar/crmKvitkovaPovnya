# Project Rules — CRM Kvitkova Povnya

> Патерни і правила специфічні для цього проєкту.
> Базова структура, стек і команди запуску — в `CLAUDE.md`.

---

## Чек-лист для нової фічі

**Перед реалізацією:**
- [ ] Чи є відповідний бізнес-кейс в `BUSINESS_LOGIC.md`?
- [ ] Чи потрібна міграція БД? (перевір справжню назву таблиці — `order`, не `orders`)
- [ ] Чи не дублює існуючий сервіс або утиліту?

**При реалізації:**
- [ ] Бізнес-логіка — в `services/`, не в `routes/`
- [ ] AJAX-відповіді через `jsonify({'success': True/False, ...})`
- [ ] Всі DB-операції огорнуті в `try/except` з `db.session.rollback()`
- [ ] При bulk-оновленні — завжди rollback при помилці

**При додаванні моделі:**
- [ ] `index=True` на колонки що використовуються у WHERE/JOIN: `delivery_date`, `status`, `client_id`, `courier_id`
- [ ] FK перевіряти по реальній назві таблиці (`order`, `user`, `client`)
- [ ] Нова міграція в `migrations/versions/` — дивись існуючі як зразок

**Перед мержем:**
- [ ] `pytest tests/unit/ -v` — всі тести зелені
- [ ] Нові тести для нової логіки

---

## Правила для сервісів

```python
# Повертати (result, error) або кидати ValueError — не мішати
def create_something(data) -> tuple[Model, None] | tuple[None, str]:
    if not data.get('field'):
        return None, 'Поле обов\'язкове'
    ...
    return obj, None

# Bulk-операції — завжди з rollback
def bulk_update(ids, data):
    try:
        for id in ids:
            obj = Model.query.get(id)
            if obj:
                obj.field = data['field']
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f'bulk_update failed: {e}')
        raise
```

---

## Правила для міграцій

```python
# Завжди перевіряй реальну назву таблиці
op.add_column('order', ...)      # ✅ правильно
op.add_column('orders', ...)     # ❌ неправильно

# FK на user/client/order — без 's'
db.ForeignKey('order.id')        # ✅
db.ForeignKey('orders.id')       # ❌

# Запуск вручну
docker compose exec web flask db upgrade
```

---

## Навігація в sidebar

Паттерн для нового пункту (`layout.html`, рядки ~178-257):

```html
<a href="/path"
   class="flex items-center gap-3 px-2 py-2 rounded-lg text-sm transition-colors
          {% if request.path.startswith('/path') %}bg-amber-50 border border-amber-200 text-amber-700
          {% else %}text-stone-600 hover:bg-stone-200 hover:text-stone-900{% endif %}"
   title="Назва">
    <i class="bi bi-icon-name text-lg flex-shrink-0"></i>
    <span class="nav-label">Назва</span>
</a>
```

---

## Toast-нотифікації

```html
{{- render_toast() }}
{{- toast_script() }}
```
```javascript
showToast('Збережено', 'success');
showToast('Помилка збереження', 'error');
```
