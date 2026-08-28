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
