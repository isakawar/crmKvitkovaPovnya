# Автопідтягування адрес (Google Places) + передача координат в оптимізатор

Дата: 2026-09-01
Гілка CRM: `feat/address-autocomplete`
Супутня гілка: `flower_route_optimizer` → `feat/accept-coordinates`

## Проблема

Менеджер вручну вводить адресу доставки в модалці створення замовлення/підписки.
Помилки та неоднозначні написання ("Мартинова" / "Мартынова", скорочення, відсутній
номер будинку) проходять валідацію. Коли така доставка потрапляє в route optimizer,
його геокодер не знаходить адресу → доставку або відкидають, або ставлять у
неправильну точку → маршрут рахується невірно.

## Ціль

1. У формах, де вводиться адреса доставки, показувати Google-автодоповнення
   (як у прикладі-скріншоті: дропдаун із варіантами "вулиця, будинок, місто, країна").
2. Зберігати разом з адресою: `latitude`, `longitude`, `google_place_id`,
   `formatted_address`.
3. Передавати координати в оптимізатор, щоб він не геокодував адресу повторно.

## Обсяг рішення

Дві частини, реалізуються послідовно (B одразу після A, не відкладається):

- **A. CRM** (`crmKvitkovaPovnya`, гілка `feat/address-autocomplete`)
- **B. Optimizer** (`flower_route_optimizer`, окрема гілка + PR)

Рішення "без власного геокодера в CRM": оптимізатор уже має `GeocodingService`
(Google + Nominatim + кеш). Записи без координат (старі рядки БД, телефонні
замовлення, ручний імпорт — усе, що йде повз новий JS-модуль) передаються в
оптимізатор без `lat/lng`, і він геокодує їх сам, як зараз. Коли є
Google-нормалізований `formatted_address` — він іде в рядок адреси і покращує
геокодинг на боці оптимізатора.

---

## Частина A — CRM

### A1. Google API

- **Places API (New)**, JS SDK, метод `AutocompleteSuggestion.fetchAutocompleteSuggestions()`
  для підказок + `Place.fetchFields(['location','formattedAddress','addressComponents'])`
  для координат обраного варіанту.
- Причина вибору Data API замість готового `PlaceAutocompleteElement`: потрібен
  власний вигляд дропдауна, що збігається з наявним стилем `.city-autocomplete-*`.
- Session tokens для білінгу (один токен на цикл "введення → вибір").
- Параметри запиту: `includedRegionCodes: ['ua']`, `language: 'uk'`,
  location bias на Київ (центр + радіус ~50 км).
- Ключ: змінна `GOOGLE_MAPS_API_KEY` уже присутня в `.env`. Додати її читання
  в `app/config.py` (`Config` + `ProductionConfig`), прокинути в шаблон через
  контекст або `<meta>`.
- У Google Cloud Console має бути увімкнено **Places API (New)**. Якщо SDK не
  завантажився / ключ невалідний — модуль тихо деградує: поле адреси лишається
  звичайним текстовим `<input>`, ніяких JS-помилок у консолі користувача не видно
  (лог у `console.warn`).

### A2. JS-модуль `app/static/js/address_autocomplete.js`

Публічний API:

```js
initAddressAutocomplete(streetInput, dropdownEl, formEl, {
    cityInput,            // <input name="city"> — автозаповнюється, якщо порожній
    buildingInput,        // optional <input name="building_number">; якщо заданий,
                          //   номер будинку йде туди, а не в streetInput
    prefix = '',          // префікс id для прихованих полів (модалки з кількома формами)
})
```

Поведінка:

- Слухає `input` на `streetInput`, debounce 250 мс, запит від 3 символів.
- Рендерить власний дропдаун (розмітка + класи як у `city_autocomplete.js`).
- Клавіатура: `ArrowUp`/`ArrowDown`/`Enter`/`Escape`, `mousedown` для вибору
  (щоб випередити `blur`).
- При виборі варіанту:
  - `Place.fetchFields(...)` → `location.lat()/lng()`, `formattedAddress`,
    `addressComponents`.
  - Заповнює `streetInput` (route + street_number, або весь рядок, якщо
    `buildingInput` не заданий); `buildingInput` — street_number.
  - Якщо `cityInput.value` порожній — ставить `locality`/`administrative_area_level_1`.
  - Пише у приховані поля форми (створюються модулем, якщо їх немає):
    `{prefix}latitude`, `{prefix}longitude`, `{prefix}google_place_id`,
    `{prefix}formatted_address`.
- Якщо після вибору користувач редагує `streetInput` вручну — приховані
  координати очищаються (`input`-хендлер порівнює поточне значення з тим, що
  було підставлено).
- На `submit` форми: якщо метод доставки — курʼєрська адреса (не самовивіз,
  не Нова Пошта) і приховані `latitude/longitude` порожні → `confirm()`
  "Адресу не підтверджено через Google. Зберегти як є?". `Cancel` → `preventDefault`.
  Це попередження, не блокування.
- Lazy-load Google Maps JS SDK: перше використання завантажує
  `https://maps.googleapis.com/maps/api/js?key=...&libraries=places&language=uk`
  (Promise-обгортка, один раз на сторінку).

### A3. Міграція БД

Одна міграція, `down_revision = 'add_wix_lead_custom_fields'` (актуальний head,
перевірено через `flask db heads`).

Додає в таблиці `subscription`, `order`, `delivery` (усі nullable):

| Колонка             | Тип             |
|---------------------|-----------------|
| `latitude`          | `NUMERIC(9, 6)` |
| `longitude`         | `NUMERIC(9, 6)` |
| `google_place_id`   | `VARCHAR(255)`  |
| `formatted_address` | `VARCHAR(500)`  |

`NUMERIC(9,6)`: діапазон України (шир. 44–53, довг. 22–41) вкладається, точність
~0.1 м. Файл міграції створюється → `git commit` → лише потім `flask db upgrade`
(правило репо).

### A4. Моделі

`app/models/subscription.py`, `order.py`, `delivery.py` — по 4 нові колонки
поруч із наявними полями адреси.

### A5. Пропагація координат

Тим самим шляхом, що й `street` зараз:

- `app/services/subscription_service.py`
  - `create_subscription` — читає 4 поля з `form`, пише в `Subscription`.
  - `_build_order(...)` / місця, де `Order(... street=subscription.street ...)` —
    додати `latitude=subscription.latitude` тощо (main.py:342, 474 еквіваленти).
  - `_build_delivery(...)` (рядок ~256) — `latitude=order.latitude ...`.
  - `create_subscription_from_import` — читає з `form`, якщо є (імпорт зазвичай
    без координат → лишаються None).
  - overrides-шлях (`build ... overrides.get('latitude') or subscription.latitude`).
- `app/services/order_service.py`
  - `create_order_and_deliveries` — читає 4 поля з `form` (рядок ~68),
    Delivery успадковує (рядок ~106).
  - `update_order` — читає 4 поля з `form` (рядок ~278); синхронізація в
    майбутні Delivery (рядок ~234) — оновлює й координати.
- `app/services/delivery_service.py`
  - `update_delivery` (рядок ~100) — якщо в `data` є `latitude` тощо, пише.

Самовивіз: координати не пишемо (як зі `street='Самовивіз'`).

### A6. Роути

`app/blueprints/orders/routes.py`:

- `order_create` (POST `/orders/new`) — нові поля вже підуть через `request.form`
  у сервіси; переконатись, що `create_order_and_deliveries` / `create_subscription`
  їх дістають.
- `order_edit` (POST) — те саме через `update_order`.
- `/orders/wix-lead/<id>/composer-data` — координат немає, не чіпаємо.

`app/blueprints/subscriptions/…` — POST-handler `_edit_modal` читає нові поля.

### A7. Передача в оптимізатор

`app/services/route_optimizer_service.py::_delivery_to_order_json(delivery)`:

```python
lat = delivery.latitude or (order.latitude if order else None)
lng = delivery.longitude or (order.longitude if order else None)
if lat is not None and lng is not None:
    item["lat"] = float(lat)
    item["lng"] = float(lng)
```

Також, коли є `formatted_address`, використовувати його як `address` (розбити на
street/house за наявними полями лишається як є — оптимізатор конкатенує назад).

Це єдине місце інтеграції: `optimize_json` та `distribute_deliveries` обидва
викликають `_delivery_to_order_json`.

### A8. UI-поверхні (повний список)

| Файл                                            | Поле адреси              | Особливість                    |
|-------------------------------------------------|-------------------------|--------------------------------|
| `orders/_composer_modal.html` + `_composer_script.html` | `#address-input` (name=street) | одне комбіноване поле, без `building_number` |
| `orders/form.html`                              | `#address-input` (name=street) + `name=building_number` | окремі поля |
| `subscriptions/_edit_modal.html`                | `#sub-edit-street` + `#sub-edit-building` | окремі поля, `prefix='sub-edit-'` |

У кожному: додати `<div class="…-autocomplete-dropdown">` під полем адреси,
4 приховані `<input type="hidden">`, підключити `address_autocomplete.js`,
викликати `initAddressAutocomplete(...)` в тому ж місці, де зараз
`initCityAutocomplete(...)`.

Перевірено, що не входить у список: `_draft_edit_modal.html` (немає полів адреси),
`routes/saved.html` (адреса read-only).

### A9. CSS

Наявний блок стилів автодоповнення (спільний із city) розширити за потреби —
іконка "будинок", дворядковий пункт (адреса + місто/країна сірим). Після змін
шаблонів — `npm run build`.

### A10. Тести (CRM)

- `tests/unit/test_order_service.py` — координати з форми осідають на Order і
  копіюються в Delivery.
- `tests/unit/test_subscription_service.py` — Subscription → Order → Delivery.
- `tests/unit/test_route_optimizer_service.py` (новий або наявний) —
  `_delivery_to_order_json` з координатами додає `lat/lng`; без координат — ні.
- Ручний прогін: кожна з 3 форм — вибрати адресу зі списку, зберегти, перевірити
  БД; ввести вручну без вибору — зʼявляється `confirm`.

---

## Частина B — flower_route_optimizer

Гілка `feat/accept-coordinates`, окремий PR. Обсяг скориговано після читання коду:
`/api/optimize/json` конвертує `OrderInput` → CSV → `read_orders`, тому просто
додати поля в `OrderInput` недостатньо — координати губляться на кроці JSON→CSV.

### B1. `main.py`

- `OrderInput` (≈ рядок 1181): `+ lat: float | None = None`, `+ lng: float | None = None`.
- `optimize_json` (≈ рядок 1339–1352): додати `lat`, `lng` у `fieldnames`
  `DictWriter` і у `writer.writerow({... "lat": o.lat if o.lat is not None else "",
  "lng": o.lng if o.lng is not None else ""})`.
- `_geocode_order` (≈ рядок 226): якщо `order.lat is not None and order.lng is not None`
  → `return (order.lat, order.lng)` без виклику `geocoder.geocode(...)`.
- `_geocode_new` (≈ рядок 805, шлях `/api/distribute`) — той самий skip.

### B2. `services/csv_service.py`

- `read_orders` (≈ рядок 42): читати опційні колонки:
  ```python
  lat = row.get("lat", "").strip()
  lng = row.get("lng", "").strip()
  order = Order(..., lat=float(lat) if lat else None, lng=float(lng) if lng else None)
  ```
- Оновити docstring зі списком колонок.

### B3. Тести (optimizer)

- `POST /api/optimize/json` з `lat/lng` у payload → геокодер не викликається
  (mock/spy на `GeocodingService.geocode`), координати доходять до розвʼязувача.
- `read_orders` з CSV, що містить `lat,lng` → `Order.lat/lng` заповнені.
- Зворотна сумісність: payload без `lat/lng` працює як раніше.

### B4. Backlog (не в цьому PR)

Прибрати JSON→CSV round-trip у `optimize_json`, передавати `list[Order]` у
`_optimize_sync` напряму. Згадувалось в архітектурному аудиті репо як окреме
джерело тертя. Не робити разом із цією задачею.

---

## Порядок робіт

1. CRM: міграція (commit) → upgrade → моделі → сервіси → JS-модуль → 3 шаблони →
   `route_optimizer_service` → тести → `npm run build`.
2. Optimizer: гілка B → зміни B1–B3 → тести → PR.
3. Інтеграційний прогін: замовлення через composer з вибором адреси → БД має
   `lat/lng` → генерація маршруту → у логах оптимізатора 0 запитів геокодера
   для цієї доставки → адреса на правильній точці.

## Ризики

- Places API (New) має бути активований у Cloud Console з білінгом; інакше
  автодоповнення мовчки не працює → передбачена деградація до звичайного поля.
- `addressComponents` для нових/приватних адрес можуть не містити `street_number` —
  тоді `formatted_address` усе одно валідний, `building_number` лишається як ввів
  менеджер.
- Розсинхрон "текст vs координати" при ручному дозаписі — обробляється очищенням
  прихованих полів + `confirm` на сабміті.
