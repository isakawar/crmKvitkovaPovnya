# Автопідтягування адрес (Google Places) + координати в оптимізатор

## Статус
done (CRM + optimizer гілки готові, потрібен деплой + Google Cloud config)

## Задача
У формах вводу адреси доставки додати Google-автодоповнення, зберігати
`latitude/longitude/google_place_id/formatted_address` на Subscription/Order/Delivery
і передавати координати в route optimizer, щоб він не геокодував адресу повторно.
Мета — прибрати помилки менеджера при ручному вводі адреси, через які маршрут
рахується невірно.

Повний дизайн: `docs/superpowers/specs/2026-09-01-address-autocomplete-design.md`

## План

### CRM (гілка feat/address-autocomplete)
- [ ] Міграція: +4 nullable колонки в `subscription`, `order`, `delivery` (commit → upgrade)
- [ ] Моделі: subscription.py, order.py, delivery.py
- [ ] `app/config.py`: `GOOGLE_MAPS_API_KEY`
- [ ] `app/static/js/address_autocomplete.js` — `initAddressAutocomplete()`
- [ ] Пропагація координат: order_service.py, subscription_service.py, delivery_service.py
- [ ] Роути: orders/routes.py, subscriptions POST-handler `_edit_modal`
- [ ] `route_optimizer_service._delivery_to_order_json` — додати lat/lng
- [ ] Шаблони: `orders/_composer_modal.html` + `_composer_script.html`, `orders/form.html`, `subscriptions/_edit_modal.html`
- [ ] CSS автодоповнення + `npm run build`
- [ ] Тести: order_service, subscription_service, route_optimizer_service

### Optimizer (гілка feat/accept-coordinates, окремий PR)
- [ ] `main.py`: OrderInput +lat/lng; optimize_json CSV writer +lat/lng; `_geocode_order` skip; `_geocode_new` skip
- [ ] `services/csv_service.py`: read_orders читає опційні lat/lng
- [ ] Тести: skip-геокодинг при переданих координатах

## Реалізація

### CRM (гілка feat/address-autocomplete)
- Міграція `add_address_coordinates` — +4 nullable колонки (`latitude` NUMERIC(9,6),
  `longitude` NUMERIC(9,6), `google_place_id` VARCHAR(255), `formatted_address` VARCHAR(500))
  у `subscription`, `order`, `delivery`. Застосована на dev.
- Моделі: `app/models/{subscription,order,delivery}.py`.
- `app/config.py` + `env.example`: `GOOGLE_MAPS_API_KEY`.
- `app/utils/address_utils.py` — `coords_from_form()`, `copy_coords()`, `COORD_FIELDS`.
- `app/static/js/address_autocomplete.js` — `initAddressAutocomplete()`, Places API (New),
  session tokens, `includedRegionCodes:['ua']`, degrade-to-plain-input, soft confirm на сабміті.
- Пропагація: `order_service` (create/update/sync), `subscription_service`
  (create/create_from_import/update/extend), `delivery_service.update_delivery`.
- `route_optimizer_service._delivery_to_order_json` — додає `lat`/`lng` (fallback delivery→order).
- Роути: `orders/routes.py` (order composer-data JSON), `subscriptions/routes.py` (sub detail JSON).
- Шаблони: `orders/_composer_modal.html` + `_composer_script.html` (create + subscription edit),
  `orders/form.html`, `layout.html` (`window.GOOGLE_MAPS_API_KEY`). Скрипт підключено в
  `orders/list.html`, `subscriptions/list.html`, `dashboard/index.html`, `integrations/leads_list.html`.
- CSS `.address-autocomplete-item` в `input.css` + `npm run build`.
- Тести: `tests/unit/test_address_coordinates.py` (10 шт).
- ⚠️ `subscriptions/_edit_modal.html` — мертвий код (нікуди не включений), НЕ чіпав.
  Реальне редагування підписки йде через composer-модалку.

### Optimizer (гілка feat/accept-coordinates, репо ~/Develop/flower_route_optimizer)
- `models/order.py` вже мав `lat/lng`; додано в `OrderInput` (`main.py`) + CSV writer у
  `optimize_json` + `read_orders` (`services/csv_service.py`).
- `_geocode_order` та `_geocode_new` повертають передані координати без запиту до геокодера.
- Тести: `tests/test_json_coordinates.py` (3 шт). Прогнав — проходять; 19 падінь у
  `test_api_optimize`/`test_api_recalculate` — прееізнуючі (baseline теж 19).
- Комміт `55a0037c`, гілка ще не змержена — потрібен PR.

## Що лишилось (деплой)
1. Google Cloud Console: увімкнути **Places API (New)** для ключа з `.env` (білінг).
2. Змержити гілку оптимізатора `feat/accept-coordinates` → задеплоїти оптимізатор.
3. CRM: `flask db upgrade` на проді (міграція вже в git), задеплоїти CRM.
   Порядок: спершу оптимізатор, потім CRM (CRM почне слати `lat/lng` — старий
   оптимізатор їх просто проігнорує, тож жорсткої залежності немає).

## Як тестувати
1. Composer: створити замовлення, ввести "Чоколівський бульвар 6", вибрати варіант зі списку.
2. Перевірити в БД: `order.latitude/longitude/google_place_id/formatted_address` заповнені; те саме в `delivery`.
3. Згенерувати маршрут → у логах оптимізатора немає запиту геокодера для цієї доставки, точка на карті правильна.
4. Ввести адресу вручну без вибору зі списку → на збереженні `confirm("Адресу не підтверджено...")`.
5. Стара форма `/orders/new` і модалка редагування підписки — та сама поведінка.

## Edge cases
- Google SDK не завантажився / ключ невалідний → поле працює як звичайний текстовий input, без JS-помилок.
- Адреса без street_number у addressComponents → formatted_address валідний, building_number як ввів менеджер.
- Ручне редагування рядка після вибору → приховані координати очищаються.
- Самовивіз / Нова Пошта → координати не пишемо, confirm не показуємо.
- Записи без координат (старі, імпорт, телефон) → йдуть в оптимізатор без lat/lng, він геокодує сам.
