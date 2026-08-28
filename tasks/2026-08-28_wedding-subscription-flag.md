# Відмітка «весільна підписка»

## Статус
done

## Задача
Дати можливість позначати підписку як весільну при створенні/редагуванні,
щоб потім фільтрувати й будувати статистику по весільних підписках.
Поле `Subscription.is_wedding` вже існувало в БД, але не проставлялося з UI.

## План
- [x] `create_subscription()` / `update_subscription()` читають `is_wedding` з форми
- [x] Чекбокс «Весільна підписка» у композері (спільний для створення й редагування)
- [x] JS: показ чекбоксу лише для сценарію «підписка», заповнення при редагуванні
- [x] Конвертація драфту → нова підписка автоматично весільна
- [x] `subscription_detail` JSON віддає `is_wedding` для заповнення модалки
- [x] `_subscription_snapshot` пише `is_wedding` в activity log

## Реалізація
- `app/services/subscription_service.py`
  - `create_subscription()` — парсинг `is_wedding` + передача в `Subscription(...)`
  - `update_subscription()` — явно виставляє `subscription.is_wedding` (True і False)
  - `_subscription_snapshot()` — додано ключ `is_wedding`
  - `create_subscription_from_import()` / `extend_subscription()` — вже підтримували, не чіпали
- `app/blueprints/subscriptions/routes.py`
  - `subscription_detail` — додано `is_wedding` у JSON
- `app/templates/orders/_composer_modal.html`
  - чекбокс `name="is_wedding"` (`#is-wedding-field` / `#is-wedding-input`)
- `app/templates/orders/_composer_script.html`
  - refs `isWeddingField` / `isWeddingInput`
  - `syncScenarioUI()` — тоглить видимість поля по `currentComposerFlow`
  - `openSubscriptionEditor()` — `isWeddingInput.checked = Boolean(subData.is_wedding)`
  - submit — `if (window._convertingDraftId) fd.set('is_wedding', 'on')`
- `app/templates/subscriptions/_draft_actions_script.html`
  - при конвертації драфту одразу ставить галочку в композері
- `npm run build`

Міграція не потрібна — колонка `is_wedding` вже є.
Драфти (`status='draft'`) навмисно не позначаються: вони виключені з усіх вибірок,
прапорець живе на справжній підписці, що створюється з драфту.

## Як тестувати
1. Нова підписка з увімкненою галочкою → в БД `subscription.is_wedding = true`,
   доставки згенеровані як звичайно.
2. Редагувати підписку, зняти/поставити галочку → значення зберігається.
3. Вкладка «Чернетки» → «Оформити» на драфті → у композері галочка вже стоїть →
   створена підписка має `is_wedding = true`, драфт видалено.
4. Разове замовлення → галочки «Весільна підписка» не видно, поведінка не змінилась.
5. CSV-імпорт весільних → як і раніше.

## Edge cases
- Галочка знята → `is_wedding` у формі відсутній → `form.get(...)` → `False` (і при
  створенні, і при редагуванні).
- `subscriptions/_edit_modal.html` — не використовується (dead code), редагування
  йде через композер; регресії немає.
- Продовження весільної підписки — `is_wedding` копіюється з батьківської (без змін).

---

## Частина 2: блок аналітики «LTV / Весільні»

### Статус
done

### Реалізація
- `app/services/reports_service.py`
  - `get_wedding_analytics(date_from, date_to)` → namespace `wedding`:
    `active_count`, `orders_in_range`, `deliveries_done`, `revenue` (delivery_charge),
    `payments` (credit з `subscription_id` ∈ весільні), `avg_collected_per_sub`,
    `max_deliveries_single_sub`, `revenue_share` (% від загального revenue).
    Діапазон фільтрує revenue/payments/deliveries/orders; `active_count` і
    `max_deliveries_single_sub` — за весь час.
  - `get_ltv_data(date_from, date_to)` → namespace `ltv` (усе за весь час):
    `avg_sub_deliveries_per_client`, `avg_all_deliveries_per_client`,
    `top_by_deliveries` (топ-10), `top_by_revenue` (топ-10, без офлайн-флориста),
    `avg_lifespan_days` (перша доставка → сьогодні), `lifespan_by_type`.
- `app/blueprints/reports/routes.py` — kwargs `wedding=`, `ltv=`
- `app/templates/reports/index.html` — вкладка «LTV / Весільні» (`tab=wedding_ltv`):
  KPI-картки весільних + KPI LTV + таблиця lifespan по типах + 2 таблиці топ-10
- `CLAUDE.md` — оновлено таблицю Reports API + список вкладок
- `npm run build`

### Відомі обмеження
- `payments` / `avg_collected_per_sub` для весільних = 0 на історичних даних
  (квітневий імпорт без привʼязки оплат). Працює для підписок від серпня 2026,
  де оплати чіпляються до підписки.
- `avg_lifespan_days` занижений — історія в базі ~4 місяці.

### Як тестувати
1. `/reports?tab=wedding_ltv` — вкладка відкривається, KPI заповнені.
2. Порівняти з ручним SQL: revenue весільних, к-ть доставлених, max доставок.
3. Змінити діапазон дат — revenue/доставки/замовлення весільних змінюються,
   LTV-блок лишається сталим.
