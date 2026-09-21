Я переглянув схему, всі моделі, міграції та ключові сервіси (billing, order, subscription, delivery, transaction, reports, csv_import). Нижче — зауваження, впорядковані за ризиком. Код не чіпав.

---

🔴 Критичне — гроші та цілісність балансу

1. client.credits — денормалізований баланс без захисту, і на ньому тримається вся історія

client.credits мутується з п'яти незалежних місць:

┌────────────────────────────┬───────────────────────────┐
│           Місце            │         Що робить         │
├────────────────────────────┼───────────────────────────┤
│ billing_service.py:109     │ - amount при доставці     │
├────────────────────────────┼───────────────────────────┤
│ transactions/routes.py:447 │ + amount при оплаті       │
├────────────────────────────┼───────────────────────────┤
│ transactions/routes.py:575 │ ± delta при редагуванні   │
├────────────────────────────┼───────────────────────────┤
│ transaction_service.py:22  │ - amount при видаленні    │
├────────────────────────────┼───────────────────────────┤
│ reports/routes.py:112,193  │ ± при ручному коригуванні │
└────────────────────────────┴───────────────────────────┘

Проблема не в самій денормалізації, а в тому, що reports_service.py:1190 виводить усю історію балансу назад від поточного credits:

balance = int(client.credits or 0) - post_paid.get(cid, 0) + post_charged.get(cid, 0)

Тобто одна розсинхронізація credits переписує не один рядок, а всю таблицю «Баланс клієнтів» за всі місяці — заднім числом і без жодного сліду. Це не помилка сама по собі, але це означає, що всі баги нижче мають ціну значно вищу за звичайну.

2. delete_transaction реверсить лише credit — а видалити можна будь-що

transaction_service.py:20-25:
if txn.transaction_type == 'credit' and txn.client:
    txn.client.credits = ... - txn.amount
db.session.delete(txn)

Роут DELETE /transactions/<id> (transactions/routes.py:605) приймає будь-який id без перевірки типу. І тут ключове: список транзакцій (routes.py:52) виключає тільки delivery_charge — а тип 'adjustment' (створюється в reports/routes.py:184) потрапляє в список і доступний до видалення. Видалили коригування → транзакція зникла, credits не повернувся → історія балансу зсунулась назавжди.

Те саме в update_transaction (routes.py:573): credits правиться лише для credit.

3. Скасування доставленої доставки не повертає гроші

delivery_service.py:140-143 — списання лише в один бік:
if new_status == 'Доставлено' and not d.delivered_at:
    d.delivered_at = ...
    charge_delivery(d)
Перевід назад у Скасовано/Очікує не створює сторно. Захист від подвійного списання є (delivered_at + guard по delivery_id), а від помилкового — немає. Зважаючи на те, що статуси міняються з телеграм-бота кур'єром, помилковий тап цілком реальний.

4. create_subscription не фіксує ціну — на відміну від усіх інших шляхів створення

resolve_charge_amount (billing_service.py:55) прямо декларує: «Зміна цін в активному PricePreset не має заднім числом переоцінювати вже створені замовлення — підписки в тому числі». Але:

┌─────────────────────────────────────┬──────────────────┐
│           Шлях створення            │  charged_amount  │
├─────────────────────────────────────┼──────────────────┤
│ create_order_and_deliveries:100     │ ✅ фіксується    │
├─────────────────────────────────────┼──────────────────┤
│ create_subscription_from_import:513 │ ✅               │
├─────────────────────────────────────┼──────────────────┤
│ extend_subscription:761             │ ✅               │
├─────────────────────────────────────┼──────────────────┤
│ create_subscription:345-390         │ ❌ не фіксується │
└─────────────────────────────────────┴──────────────────┘

Основний шлях створення підписки через UI лишає charged_amount = NULL → фолбек на живий прайс → підняли ціни, і всі недоставлені доставки старих підписок перераховуються за новим прайсом. Це рівно той сценарій, який docstring обіцяє не допускати.

5. update_order не перераховує charged_amount

update_subscription:971 перераховує (order.charged_amount = get_order_price(order)), а order_service.update_order:255-337 — ні. Змінили розмір разового замовлення S → XXL, списалась стара сума.

6. extend_subscription ігнорує delivery_count

subscription_service.py:678:
dates = build_delivery_dates(first_next, subscription.type, delivery_day)  # завжди рівно 4
але delivery_count=subscription.delivery_count or 4 (рядок 719) копіюється з батька. Підписка на 8 доставок при продовженні дає 4 замовлення з полем delivery_count=8. build_delivery_dates_n існує поруч і саме для цього.

7. Видалення замовлення з фото або сертифікатом падає на FK

order_photos.order_id і certificates.order_id — звичайні FK без ON DELETE (міграції add_order_photos_table.py:20, add_certificates_table.py:33). delete_order (order_service.py:340) чистить Delivery, RouteDelivery, RecipientPhone — і все. Замовлення з фото → IntegrityError. Те саме в delete_subscription.

---

🟠 Схема БД

8. Таблиця transaction — нуль індексів

Я перевірив усі 75 міграцій: жодного create_index на transaction. Це найгарячіша таблиця звітів — reports_service.py б'є по ній щонайменше 15 разів на один рендер /reports, майже всі запити у формі WHERE transaction_type = ? AND date BETWEEN ? AND ?. Мінімум що потрібно: (transaction_type, date), client_id, delivery_id.

9. Таблиця subscription — теж нуль індексів

Включно з client_id, по якому йде join у get_client_revenue_breakdown, get_subscriptions, get_subscriptions_needing_renewal. order і delivery індекси отримали (add_performance_indexes.py), а subscription і transaction — ні. Виглядає як просто пропущене, а не як рішення.

Також бракує: order.created_at (усі breakdown-и в get_orders_data фільтрують по ньому), order.delivery_date, client.phone (пошук через .contains()).

10. Жодного CHECK/Enum на статуси — і це вже вистрілило

transaction_type, delivery.status, subscription.status, size, delivery_method, florist_status — вільні varchar. Статусні рядки українською розкидані по коду 180+ разів літералами.

Конкретний доказ, що це не теоретично: докстрінг Transaction заявляє 'credit' | 'debit' | 'delivery_charge' | 'transfer', а в БД живе п'ятий тип 'adjustment', доданий у reports/routes.py. Саме через нього працює баг №2 — код, написаний під чотири типи, мовчки обробляє п'ятий неправильно.

11. Delivery.client_id дублює Order.client_id і розсинхронізовується

update_order:267 міняє order.client_id, sync_order_to_active_deliveries (:226) — не міняє delivery.client_id. Далі get_florist_approved_pending:247 джойнить клієнта саме через Delivery.client_id:

.join(Client, Client.id == Delivery.client_id)

а get_overdue_unclosed_deliveries:211 — через Order.client_id. Два екрани покажуть різних клієнтів для тієї самої доставки. Білінг при цьому бере order.client_id — тобто гроші підуть правильному, а флорист побачить неправильного.

12. Унікальність контактів клієнта тільки на рівні застосунку — і імпорт її обходить

_validate_contact_fields (client_service.py:99) — case-insensitive, з обробкою @. А csv_import_service.py:595 створює Client() напряму, після пошуку через find_existing_client:298, який робить filter_by(instagram=...) — точний, case-sensitive збіг. Ivanna та ivanna в БД перевірки не пройдуть, а імпортом заведуться як два клієнти. З урахуванням того, що на клієнті висить баланс — це роздвоєння грошей.

Плюс func.lower(Client.instagram) == ... не використовує ix_client_instagram (індекс по колонці, не по виразу) — seq scan при кожному створенні/редагуванні клієнта.

13. settings як універсальний довідник + CASCADE

settings тримає одночасно розміри, типи витрат, рахунки оплати. На неї дивляться prices.size_id, transaction.expense_type_id, transaction.payment_account_id, transaction.target_payment_account_id, florist_sale.payment_account_id. При цьому prices.size_id має ondelete='CASCADE' — видалення розміру в налаштуваннях тихо зносить прайси по всіх пресетах. А transaction.payment_account_id — без ondelete взагалі, тобто видалення рахунку впаде на FK.

Я розумію, що це свідомий патерн «одна таблиця-довідник». Але тоді вона мінімум потребує UNIQUE(type, value) (зараз його немає — два однакові розміри створюються без проблем, і Settings.query.filter_by(type='size', value=...).first() у get_order_price:30 мовчки візьме перший-ліпший) і RESTRICT замість CASCADE там, де на запис посилаються гроші.

14. Дрібніше, але варте окремого тікета

- transaction.expense_type (varchar) живе поруч із expense_type_id. update_transaction:584 пише в обидва. Legacy-колонка, яку досі годують — джерело майбутньої розбіжності.
- Генерація кодів (certificate.py:63, promo_code.py:33): ORDER BY id DESC замість сортування за кодом + читання-модифікація-запис без локу. При збоях нумерації або паралельному створенні → колізія по unique коду.
- route_deliveries: немає UNIQUE(route_id, delivery_id), немає індексу на delivery_id — а RouteDelivery.query.filter_by(delivery_id=...) викликається у 4 місцях (reschedule, resume, delete). Одна доставка може опинитись у двох маршрутах одночасно.
- order.delivery_date протухає: apply_reschedule_plan:246 свідомо оновлює тільки Delivery.delivery_date («source of truth» у докстрінгу). Рішення зрозуміле, але колонку далі читають у transactions/routes.py:292,304 і subscriptions/routes.py:230,286. Якщо це джерело правди — колонку на Order варто прибрати, а не лишати як пастку.
- florist_sale (florist/routes.py:411) жорстко ставить date=date.today() — заднім числом продаж не внести. Схоже на свідоме обмеження, але тоді і правити продаж теж неможливо.
- Округлення: get_order_price:52 робить int(base * (1 - discount/100)) — обрізання вниз, не банківське округлення. При 5% на 1000 грн різниця копійчана, але charged_amount — Integer, а transaction.amount і client.credits — Numeric(10,2). Змішування типів у грошових розрахунках краще прибрати.
- Немає updated_at на order, subscription, client, transaction. activity_log частково це компенсує, але тільки для дій через UI.

---

🟡 Документація розійшлася з кодом

CLAUDE.md стверджує:

▎ Subscriptions — not a separate model. A subscription is an Order with delivery_type in ('Weekly', 'Monthly', 'Bi-weekly'). On creation, 4 deliveries are auto-generated.

Фактично: є повноцінна модель Subscription (108 рядків, окрема таблиця), Order.delivery_type не існує взагалі, а кількість доставок керується delivery_count (1–52). Це не косметика — інструкція навпростець веде до неправильних запитів у будь-якому новому коді.

---

Що я б робив першим

1. №2 + №3 (сторно) — реальні втрати грошей просто зараз, фікс локальний.
2. №8 + №9 (індекси на transaction, subscription) — одна міграція, найбільший ефект на швидкість /reports.
3. №4 + №5 (charged_amount) — два рядки, прибирають ретроактивну переоцінку.
4. №7 (падіння при видаленні) — ON DELETE CASCADE на order_photos, SET NULL на certificates.
5. №10 (CHECK-констрейнти на статуси) — найбільша робота, але вона закриває цілий клас майбутніх багів на кшталт 'adjustment'.

Якщо скажеш, з чого починаємо — складу детальний план по конкретному пункту (міграції + правки сервісів + як тестувати) і після твого «ок» реалізую.

