# Автопідтягування адрес (Google Places) + координати в оптимізатор

## Статус
in_progress

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
_(заповнюється по ходу)_

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
