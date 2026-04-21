# Health Report: crmKvitkovaPovnya

Scanned: 2026-04-21 22:41
Total findings: 146 (actionable: 128)

🟠 high: 1 | 🟡 medium: 86 | 🔵 low: 41 | ℹ️ info: 18

**Files:** 238
**Entry points:** package.json, run.py, .agents/skills/qa-expert/scripts/calculate_metrics.py

## Recommended action order

1. **HIGH:** split monster files (1 items)
2. reduce tech debt (31 items)
3. remove unused imports (20 items)
4. remove dead code (17 items)
5. extract duplicates (9 items)
6. split large files (5 items)
7. modules (4 items)

---

## 🟠 HIGH (1)

> Monster files are hard for AI to work with — context window limits mean Claude can't see the whole file at once. Split to improve AI-assisted development.

- [ ] **Monster: app/blueprints/orders/routes.py**
  - app/blueprints/orders/routes.py — 1293 lines, 29 functions.
  - **Fix (Python docs):**
    ### Package Directory Structure - Python Module Organization
    Source: https://github.com/python/cpython/blob/main/Doc/reference/import.rst
    Shows the recommended directory layout for a Python package with subpackages and modules. This structure is used as reference for understanding relative import paths and module organization.
    ```text
    package/
        __init__.py
        subpackage1/
            __init__.py
            moduleX.py
            moduleY.py
        subpackage2/
            __init__.py


## 🟡 MEDIUM (86)

- [ ] **Circular: app/blueprints/certificates/__init__.py ↔ app/blueprints/certificates/routes.py**
  - app/blueprints/certificates/__init__.py imports app/blueprints/certificates/routes.py, and app/blueprints/certificates/routes.py imports app/blueprints/certificates/__init__.py.
  - **Fix (Python docs):**
    ### Example of Mutually Importing Python Modules (Problematic)
    Source: https://github.com/python/cpython/blob/main/Doc/faq/programming.rst
    This snippet illustrates a common issue with circular imports between two Python modules, `foo.py` and `bar.py`. When `foo` imports `bar` and `bar` imports `foo`, attempting to access variables from a partially initialized module can lead to `AttributeError` or other import-related errors.
    ```python
    from bar import bar_var
    foo_var = 1
    ```
    ```python
    from foo import foo_var
    bar_var = 2
    ```
    --------------------------------

- [ ] **Circular: app/blueprints/ai_agent/__init__.py ↔ app/blueprints/ai_agent/routes.py**
  - app/blueprints/ai_agent/__init__.py imports app/blueprints/ai_agent/routes.py, and app/blueprints/ai_agent/routes.py imports app/blueprints/ai_agent/__init__.py.
  - **Fix (Python docs):**
    ### Example of Mutually Importing Python Modules (Problematic)
    Source: https://github.com/python/cpython/blob/main/Doc/faq/programming.rst
    This snippet illustrates a common issue with circular imports between two Python modules, `foo.py` and `bar.py`. When `foo` imports `bar` and `bar` imports `foo`, attempting to access variables from a partially initialized module can lead to `AttributeError` or other import-related errors.
    ```python
    from bar import bar_var
    foo_var = 1
    ```
    ```python
    from foo import foo_var
    bar_var = 2
    ```
    --------------------------------

- [ ] **Circular: app/blueprints/subscriptions/__init__.py ↔ app/blueprints/subscriptions/routes.py**
  - app/blueprints/subscriptions/__init__.py imports app/blueprints/subscriptions/routes.py, and app/blueprints/subscriptions/routes.py imports app/blueprints/subscriptions/__init__.py.
  - **Fix (Python docs):**
    ### Example of Mutually Importing Python Modules (Problematic)
    Source: https://github.com/python/cpython/blob/main/Doc/faq/programming.rst
    This snippet illustrates a common issue with circular imports between two Python modules, `foo.py` and `bar.py`. When `foo` imports `bar` and `bar` imports `foo`, attempting to access variables from a partially initialized module can lead to `AttributeError` or other import-related errors.
    ```python
    from bar import bar_var
    foo_var = 1
    ```
    ```python
    from foo import foo_var
    bar_var = 2
    ```
    --------------------------------

- [ ] **Circular: app/blueprints/transactions/__init__.py ↔ app/blueprints/transactions/routes.py**
  - app/blueprints/transactions/__init__.py imports app/blueprints/transactions/routes.py, and app/blueprints/transactions/routes.py imports app/blueprints/transactions/__init__.py.
  - **Fix (Python docs):**
    ### Example of Mutually Importing Python Modules (Problematic)
    Source: https://github.com/python/cpython/blob/main/Doc/faq/programming.rst
    This snippet illustrates a common issue with circular imports between two Python modules, `foo.py` and `bar.py`. When `foo` imports `bar` and `bar` imports `foo`, attempting to access variables from a partially initialized module can lead to `AttributeError` or other import-related errors.
    ```python
    from bar import bar_var
    foo_var = 1
    ```
    ```python
    from foo import foo_var
    bar_var = 2
    ```
    --------------------------------

> Monster files are hard for AI to work with — context window limits mean Claude can't see the whole file at once. Split to improve AI-assisted development.

- [ ] **Monster: app/telegram_bot/handlers.py**
  - app/telegram_bot/handlers.py — 939 lines, 31 functions.
  - **Fix (Python docs):**
    ### Package Directory Structure - Python Module Organization
    Source: https://github.com/python/cpython/blob/main/Doc/reference/import.rst
    Shows the recommended directory layout for a Python package with subpackages and modules. This structure is used as reference for understanding relative import paths and module organization.
    ```text
    package/
        __init__.py
        subpackage1/
            __init__.py
            moduleX.py
            moduleY.py
        subpackage2/
            __init__.py

- [ ] **Monster: app/services/ai_agent_service.py**
  - app/services/ai_agent_service.py — 808 lines, 18 functions.
  - **Fix (Python docs):**
    ### Package Directory Structure - Python Module Organization
    Source: https://github.com/python/cpython/blob/main/Doc/reference/import.rst
    Shows the recommended directory layout for a Python package with subpackages and modules. This structure is used as reference for understanding relative import paths and module organization.
    ```text
    package/
        __init__.py
        subpackage1/
            __init__.py
            moduleX.py
            moduleY.py
        subpackage2/
            __init__.py

- [ ] **Monster: app/static/js/clients.js**
  - app/static/js/clients.js — 601 lines, 53 functions.
  - **Fix (Python docs):**
    ### Package Directory Structure - Python Module Organization
    Source: https://github.com/python/cpython/blob/main/Doc/reference/import.rst
    Shows the recommended directory layout for a Python package with subpackages and modules. This structure is used as reference for understanding relative import paths and module organization.
    ```text
    package/
        __init__.py
        subpackage1/
            __init__.py
            moduleX.py
            moduleY.py
        subpackage2/
            __init__.py

- [ ] **Monster: app/services/csv_import_service.py**
  - app/services/csv_import_service.py — 524 lines, 17 functions.
  - **Fix (Python docs):**
    ### Package Directory Structure - Python Module Organization
    Source: https://github.com/python/cpython/blob/main/Doc/reference/import.rst
    Shows the recommended directory layout for a Python package with subpackages and modules. This structure is used as reference for understanding relative import paths and module organization.
    ```text
    package/
        __init__.py
        subpackage1/
            __init__.py
            moduleX.py
            moduleY.py
        subpackage2/
            __init__.py

- [ ] **Monster: app/services/subscription_service.py**
  - app/services/subscription_service.py — 521 lines, 16 functions.
  - **Fix (Python docs):**
    ### Package Directory Structure - Python Module Organization
    Source: https://github.com/python/cpython/blob/main/Doc/reference/import.rst
    Shows the recommended directory layout for a Python package with subpackages and modules. This structure is used as reference for understanding relative import paths and module organization.
    ```text
    package/
        __init__.py
        subpackage1/
            __init__.py
            moduleX.py
            moduleY.py
        subpackage2/
            __init__.py

> Unused imports add noise, slow down IDE indexing, and can mask real dependencies. Safe to remove after verifying they're not side-effect imports.

- [ ] **Unused: engine_from_config**
  - engine_from_config imported in migrations/env.py:3 but never used.

- [ ] **Unused: pool**
  - pool imported in migrations/env.py:4 but never used.

- [ ] **Unused: sa**
  - sa imported in migrations/versions/add_transaction_type_columns.py:8 but never used.

- [ ] **Unused: sa**
  - sa imported in migrations/versions/add_test_delivery_type.py:9 but never used.

- [ ] **Unused: op**
  - op imported in migrations/versions/add_subscription_is_wedding.py:8 but never used.

- [ ] **Unused: sa**
  - sa imported in migrations/versions/add_subscription_is_wedding.py:9 but never used.

- [ ] **Unused: redirect**
  - redirect imported in app/blueprints/clients/routes.py:1 but never used.

- [ ] **Unused: url_for**
  - url_for imported in app/blueprints/clients/routes.py:1 but never used.

- [ ] **Unused: get_all_clients**
  - get_all_clients imported in app/blueprints/clients/routes.py:3 but never used.

- [ ] **Unused: ROLE_PERMISSIONS**
  - ROLE_PERMISSIONS imported in app/blueprints/settings/routes.py:5 but never used.

- [ ] **Unused: datetime**
  - datetime imported in app/blueprints/certificates/routes.py:1 but never used.

- [ ] **Unused: Client**
  - Client imported in app/blueprints/certificates/routes.py:11 but never used.

- [ ] **Unused: Delivery**
  - Delivery imported in app/blueprints/subscriptions/routes.py:9 but never used.

- [ ] **Unused: func**
  - func imported in app/blueprints/orders/routes.py:562 but never used.

- [ ] **Unused: Order**
  - Order imported in app/blueprints/routes/routes.py:61 but never used.

- [ ] **Unused: Client**
  - Client imported in app/blueprints/routes/routes.py:62 but never used.

- [ ] **Unused: Order**
  - Order imported in app/telegram_bot/services.py:12 but never used.

- [ ] **Unused: Client**
  - Client imported in app/telegram_bot/services.py:13 but never used.

- [ ] **Unused: Optional**
  - Optional imported in app/telegram_bot/notification_service.py:8 but never used.

- [ ] **Unused: Dict**
  - Dict imported in app/telegram_bot/notification_service.py:8 but never used.

> Dead code confuses AI assistants and developers. If a function isn't called, it's either forgotten or accessed via framework magic — verify before deleting.

- [ ] **Unused class: TelegramNotificationService**
  - class TelegramNotificationService in app/telegram_bot/notification_service.py — exists but nobody uses it.

- [ ] **Unused method: send_delivery_notifications**
  - send_delivery_notifications() in app/telegram_bot/notification_service.py — defined but never called anywhere in the project.

- [ ] **Unused method: help_command**
  - help_command() in app/telegram_bot/handlers.py — defined but never called anywhere in the project.

- [ ] **Unused method: profile_command**
  - profile_command() in app/telegram_bot/handlers.py — defined but never called anywhere in the project.

- [ ] **Unused method: deliveries_command**
  - deliveries_command() in app/telegram_bot/handlers.py — defined but never called anywhere in the project.

- [ ] **Unused method: today_command**
  - today_command() in app/telegram_bot/handlers.py — defined but never called anywhere in the project.

- [ ] **Unused method: tomorrow_command**
  - tomorrow_command() in app/telegram_bot/handlers.py — defined but never called anywhere in the project.

- [ ] **Unused method: week_command**
  - week_command() in app/telegram_bot/handlers.py — defined but never called anywhere in the project.

- [ ] **Unused method: edit_message**
  - edit_message() in app/telegram_bot/bot.py — defined but never called anywhere in the project.

- [ ] **Unused function: generate_delivery_dates**
  - generate_delivery_dates() in app/utils/date_utils.py — defined but never called anywhere in the project.

- [ ] **Unused function: setup_logging**
  - setup_logging() in app/utils/logger.py — defined but never called anywhere in the project.

- [ ] **Unused function: initCityAutocomplete**
  - initCityAutocomplete() in app/static/js/city_autocomplete.js — defined but never called anywhere in the project.

- [ ] **Unused function: detect_delivery_method**
  - detect_delivery_method() in app/services/csv_import_service.py — defined but never called anywhere in the project.

- [ ] **Unused function: paginate_orders**
  - paginate_orders() in app/services/order_service.py — defined but never called anywhere in the project.

- [ ] **Unused function: get_clients**
  - get_clients() in app/services/client_service.py — defined but never called anywhere in the project.

- [ ] **Unused function: get_delivery_by_id**
  - get_delivery_by_id() in app/services/delivery_service.py — defined but never called anywhere in the project.

- [ ] **Unused function: get_all_deliveries_ordered**
  - get_all_deliveries_ordered() in app/services/delivery_service.py — defined but never called anywhere in the project.

> Duplicated code means fixing a bug in one place leaves the same bug alive in the copy. Extract shared logic into a common module.

- [ ] **4 duplicate blocks: .agents/skills/qa-expert/scripts/init_qa_project.py ↔ .claude/skills/qa-expert/scripts/init_qa_project.py**
  - Total: ~469 duplicated lines. Extract shared logic into a common module.
  - Lines: ↔3 (290L), ↔294 (119L), ↔414 (45L), ↔460 (15L)

- [ ] **2 duplicate blocks: .agents/skills/qa-expert/scripts/calculate_metrics.py ↔ .claude/skills/qa-expert/scripts/calculate_metrics.py**
  - Total: ~83 duplicated lines. Extract shared logic into a common module.
  - Lines: ↔3 (62L), ↔68 (21L)

- [ ] **2 duplicate blocks: app/services/order_service.py ↔ app/services/subscription_service.py**
  - Total: ~29 duplicated lines. Extract shared logic into a common module.
  - Lines: ↔219 (16L), ↔270 (13L)

- [ ] **Duplicate: app/models/order.py ↔ app/models/subscription.py (13 lines)**
  - 13 duplicate lines: app/models/order.py:13 and app/models/subscription.py:21.

> Missing type hints make AI code generation less accurate — Claude guesses parameter types instead of knowing them. Add types to improve AI output.

- [ ] **_parse_client_form() — 1 params without types, no return type**
  - _parse_client_form() in app/blueprints/clients/routes.py:44 — 1 params without types, no return type.

- [ ] **get_client() — 1 params without types, no return type**
  - get_client() in app/blueprints/clients/routes.py:80 — 1 params without types, no return type.

- [ ] **client_update() — 1 params without types, no return type**
  - client_update() in app/blueprints/clients/routes.py:99 — 1 params without types, no return type.

- [ ] **client_delete() — 1 params without types, no return type**
  - client_delete() in app/blueprints/clients/routes.py:111 — 1 params without types, no return type.

- [ ] **delete_setting() — 1 params without types, no return type**
  - delete_setting() in app/blueprints/settings/routes.py:170 — 1 params without types, no return type.

- [ ] **toggle_user_active() — 1 params without types, no return type**
  - toggle_user_active() in app/blueprints/settings/routes.py:320 — 1 params without types, no return type.

- [ ] **change_user_password() — 1 params without types, no return type**
  - change_user_password() in app/blueprints/settings/routes.py:332 — 1 params without types, no return type.

- [ ] **_parse_selected_date() — 2 params without types, no return type**
  - _parse_selected_date() in app/blueprints/florist/routes.py:33 — 2 params without types, no return type.

- [ ] **_build_subscription_delivery_index() — 1 params without types, no return type**
  - _build_subscription_delivery_index() in app/blueprints/florist/routes.py:42 — 1 params without types, no return type.

- [ ] **_parse_month() — 1 params without types, no return type**
  - _parse_month() in app/blueprints/florist/routes.py:198 — 1 params without types, no return type.

- [ ] **_month_bounds() — 1 params without types, no return type**
  - _month_bounds() in app/blueprints/florist/routes.py:210 — 1 params without types, no return type.

- [ ] **_adjacent_months() — 1 params without types, no return type**
  - _adjacent_months() in app/blueprints/florist/routes.py:218 — 1 params without types, no return type.

- [ ] **florist_sales_edit() — 1 params without types, no return type**
  - florist_sales_edit() in app/blueprints/florist/routes.py:345 — 1 params without types, no return type.

- [ ] **toggle_courier_status() — 1 params without types, no return type**
  - toggle_courier_status() in app/blueprints/couriers/routes.py:91 — 1 params without types, no return type.

- [ ] **delete_courier() — 1 params without types, no return type**
  - delete_courier() in app/blueprints/couriers/routes.py:115 — 1 params without types, no return type.

- [ ] **edit_courier() — 1 params without types, no return type**
  - edit_courier() in app/blueprints/couriers/routes.py:150 — 1 params without types, no return type.

- [ ] **reset_courier_telegram() — 1 params without types, no return type**
  - reset_courier_telegram() in app/blueprints/couriers/routes.py:216 — 1 params without types, no return type.

- [ ] **certificate_detail() — 1 params without types, no return type**
  - certificate_detail() in app/blueprints/certificates/routes.py:131 — 1 params without types, no return type.

- [ ] **update_certificate() — 1 params without types, no return type**
  - update_certificate() in app/blueprints/certificates/routes.py:170 — 1 params without types, no return type.

- [ ] **_format_address() — 5 params without types, no return type**
  - _format_address() in app/blueprints/subscriptions/routes.py:25 — 5 params without types, no return type.

- [ ] **subscription_draft_edit() — 1 params without types, no return type**
  - subscription_draft_edit() in app/blueprints/subscriptions/routes.py:137 — 1 params without types, no return type.

- [ ] **subscription_detail() — 1 params without types, no return type**
  - subscription_detail() in app/blueprints/subscriptions/routes.py:163 — 1 params without types, no return type.

- [ ] **subscription_extend() — 1 params without types, no return type**
  - subscription_extend() in app/blueprints/subscriptions/routes.py:282 — 1 params without types, no return type.

- [ ] **subscription_delete() — 1 params without types, no return type**
  - subscription_delete() in app/blueprints/subscriptions/routes.py:300 — 1 params without types, no return type.

- [ ] **update_subscription_followup() — 1 params without types, no return type**
  - update_subscription_followup() in app/blueprints/dashboard/routes.py:231 — 1 params without types, no return type.

- [ ] **order_edit() — 1 params without types, no return type**
  - order_edit() in app/blueprints/orders/routes.py:302 — 1 params without types, no return type.

- [ ] **order_dependencies() — 1 params without types, no return type**
  - order_dependencies() in app/blueprints/orders/routes.py:368 — 1 params without types, no return type.

- [ ] **order_delete() — 1 params without types, no return type**
  - order_delete() in app/blueprints/orders/routes.py:393 — 1 params without types, no return type.

- [ ] **update_order_bouquet_type() — 1 params without types, no return type**
  - update_order_bouquet_type() in app/blueprints/orders/routes.py:401 — 1 params without types, no return type.

- [ ] **delivery_dependencies() — 1 params without types, no return type**
  - delivery_dependencies() in app/blueprints/orders/routes.py:411 — 1 params without types, no return type.

> Bare except/empty catch blocks silently swallow errors. When something breaks, you won't know what or where. Log or handle specifically.

- [ ] **bare_except: app/__init__.py:19**
  - app/__init__.py:19 — Bare except catches everything including KeyboardInterrupt.


## 🔵 LOW (41)

- [ ] **Orphan: app/utils/date_utils.py**
  - app/utils/date_utils.py — nobody imports it, not an entry point.

- [ ] **Orphan: app/telegram_bot/notification_service.py**
  - app/telegram_bot/notification_service.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/add_test_delivery_type.py**
  - migrations/versions/add_test_delivery_type.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/initial_postgresql_migration.py**
  - migrations/versions/initial_postgresql_migration.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/add_delivery_method.py**
  - migrations/versions/add_delivery_method.py — nobody imports it, not an entry point.

> Bare except/empty catch blocks silently swallow errors. When something breaks, you won't know what or where. Log or handle specifically.

- [ ] **except_pass: app/blueprints/orders/routes.py:106**
  - app/blueprints/orders/routes.py:106 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:117**
  - app/blueprints/orders/routes.py:117 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:324**
  - app/blueprints/orders/routes.py:324 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:537**
  - app/blueprints/orders/routes.py:537 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:702**
  - app/blueprints/orders/routes.py:702 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1004**
  - app/blueprints/orders/routes.py:1004 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1016**
  - app/blueprints/orders/routes.py:1016 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1045**
  - app/blueprints/orders/routes.py:1045 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1215**
  - app/blueprints/orders/routes.py:1215 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1258**
  - app/blueprints/orders/routes.py:1258 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1286**
  - app/blueprints/orders/routes.py:1286 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1294**
  - app/blueprints/orders/routes.py:1294 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1317**
  - app/blueprints/orders/routes.py:1317 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1381**
  - app/blueprints/orders/routes.py:1381 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/orders/routes.py:1388**
  - app/blueprints/orders/routes.py:1388 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/routes/routes.py:25**
  - app/blueprints/routes/routes.py:25 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/routes/routes.py:37**
  - app/blueprints/routes/routes.py:37 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/blueprints/routes/routes.py:333**
  - app/blueprints/routes/routes.py:333 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/csv_import_service.py:388**
  - app/services/csv_import_service.py:388 — except with only 'pass' — silently swallows errors.

> Hardcoded values (URLs, ports, keys) break when environments change. Extract to config/env vars.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:16**
  - app/blueprints/routes/routes.py:16 — https://api.telegram.org/bot{bot_token}/sendMessage.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:31**
  - app/blueprints/routes/routes.py:31 — https://api.telegram.org/bot{bot_token}/editMessageText.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:258**
  - app/blueprints/routes/routes.py:258 — https://www.google.com/maps/dir/.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:328**
  - app/blueprints/routes/routes.py:328 — https://www.google.com/maps/dir/.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:330**
  - app/blueprints/routes/routes.py:330 — https://tinyurl.com/api-create.php.

- [ ] **Hardcoded url: app/config.py:26**
  - app/config.py:26 — https://openrouter.ai/api/v1.

- [ ] **Hardcoded url: app/config.py:54**
  - app/config.py:54 — https://openrouter.ai/api/v1.

- [ ] **Hardcoded url: app/telegram_bot/handlers.py:1107**
  - app/telegram_bot/handlers.py:1107 — https://www.google.com/maps/dir/.

- [ ] **Hardcoded url: app/telegram_bot/keyboards.py:133**
  - app/telegram_bot/keyboards.py:133 — https://maps.google.com/maps?q={encoded_address}.

- [ ] **Hardcoded url: app/telegram_bot/keyboards.py:136**
  - app/telegram_bot/keyboards.py:136 — https://waze.com/ul?q={encoded_address}.

- [ ] **Hardcoded url: app/telegram_bot/keyboards.py:144**
  - app/telegram_bot/keyboards.py:144 — http://maps.apple.com/?q={encoded_address}.

> Single-method classes and deep nesting add complexity without value. Simplify to plain functions where possible.

- [ ] **tiny_file: app/utils/decorators.py**
  - app/utils/decorators.py — 12 lines, 1 function.

> Giant commits are hard to review, hard to revert, and hard for AI to understand. Keep commits focused on one change.

- [ ] **Big commit: c436a28 (4798 lines)**
  - Commit 'change telegramm message' changed 4798 lines.

- [ ] **.gitignore missing: *.pyc**
  - .gitignore is missing: *.pyc.

- [ ] **README incomplete: missing installation instructions**
  - README exists (254 lines) but missing: installation instructions.

- [ ] **Unused in requirements.txt: apscheduler, flask_wtf, gunicorn**
  - In requirements.txt but not imported: apscheduler, flask_wtf, gunicorn, psycopg2_binary, pytest.

- [ ] **Deprecated 'version' in docker-compose.yml**
  - docker-compose.yml: 'version' field is deprecated in Docker Compose v2+.


---

## ⚠️ Possible false positives

The scanner uses static analysis and may flag valid code. Check these before blindly fixing:

- **map.modules**: Orphan detection doesn't track dynamic imports (importlib, __import__), lazy imports inside functions, or framework auto-discovery (Django admin autodiscover, pytest conftest). Files like `main.jsx`, `index.js`, `mongo-init.js` are often entry points loaded by bundlers or Docker — not real orphans.
- **dead.unused_imports**: Scanner may flag imports used only as type annotations in complex generics, or side-effect imports (e.g. model registration). Verify before deleting — check if the import is used in type hints, decorators, or has side effects on import.
- **dead.unused_definitions**: Functions/methods called dynamically (getattr, signals, event handlers) or exposed as public API may be flagged. Also: celery tasks discovered by name, pytest fixtures in conftest.py, and Django/DRF auto-discovered methods. Verify the function isn't called via string name or framework magic.
- **debt.no_types**: FastAPI/Flask endpoints with @router decorators get return types from the decorator (response_model=). Scanner skips these, but custom decorators may still trigger false alerts.

---

<details>
<summary>ℹ️ Info (18 items)</summary>

- **Project Map**: In your project: 238 files. Most common: .py (126). This is just context — now you know what's inside.
- **Entry Points**: Entry point = the file where everything starts. Like doors to a building. You have 9.
- **Hub: app/extensions.py**: app/extensions.py is imported by 42 files. This is your most important module. Break it — break everything.
- **Hub: app/models/__init__.py**: app/models/__init__.py is imported by 25 files. This is your most important module. Break it — break everything.
- **Hub: app/models/delivery_route.py**: app/models/delivery_route.py is imported by 14 files. This is your most important module. Break it — break everything.
- **Dependencies up to date**: All checked dependencies are on latest versions.
- **Tests: 15 files (pytest)**: 15 test files found (15 Python). Framework: pytest.
- **Session: 7 commits, ~23 files touched**: Last 8 hours: 7 commits, ~23 files modified.
- **Before building — search first**: Before writing a new feature: google it. Check GitHub repos, PyPI, npm. Someone probably already built what you need. Don't reinvent the wheel — steal the wheel.
- **Git: clean working tree**: Everything is committed. Clean slate.
- **3 unmerged branches**: Branches not merged: feat/billing, feat/draft-subscriptions-on-orders, redisigne/ui. Merge or delete them to keep things clean.
- **Git commands you need right now**: git log --oneline -5 — see recent history | git diff — see what changed since last commit
- **UI Element Dictionary available**: Frontend project detected. Can't explain to AI which button to change? Open the UI Dictionary — 20 elements with names, pictures, and example prompts.
- **Unknown packages: flask_sqlalchemy, flask_wtf, flask_migrate**: AI might not know these packages: flask_sqlalchemy (pypi), flask_wtf (pypi), flask_migrate (pypi), python_dotenv (pypi), python_telegram_bot (pypi) (+3 more). Fetch their docs so AI understands your stack.
### LLM Context Summary

Copy this to give AI context about your project:
# Project: crmKvitkovaPovnya

**Stack:** Python, JavaScript/TypeScript, Docker

**Size:** 238 files, 71 dirs

**Entry points:**
- `package.json` — Node.js project config (scripts: dev)
- `run.py` — Python main module
- `.agents/skills/qa-expert/scripts/calculate_metrics.py` — Python script with __main__ guard
- `.agents/skills/qa-expert/scripts/init_qa_project.py` — Python script with __main__ guard
- `.claude/skills/qa-expert/scripts/calculate_metrics.py` — Python script with __main__ guard

**Key modules:**
- `app/extensions.py` (imported by 42 files)
- `app/models/__init__.py` (imported by 25 files)
- `app/models/delivery_route.py` (imported by 14 files)
- `app/models/subscription.py` (imported by 14 files)
- `app/models/delivery.py` (imported by 11 files)

- **Lighthouse — run manually**: Lighthouse can check performance, accessibility, SEO — start your dev server and run: npx lighthouse http://localhost:3000 --output=json --chrome-flags='--headless'
- **pa11y — run manually**: pa11y checks WCAG accessibility — blind users, screen readers, keyboard nav. Start your dev server and run: npx pa11y http://localhost:3000 --reporter json
- **Config Files**: One .env file — that's clean.

</details>

---

## How to use this report with AI

Paste this file to Claude/Cursor and say:
```
Fix the issues in this health report, starting from HIGH severity.
Skip items marked as possible false positives.
```

---
*Scanned: [crmKvitkovaPovnya](https://github.com/isakawar/crmKvitkovaPovnya) · Generated by [fartrun](https://github.com/ChuprinaDaria/Vibecode-Cleaner-Fartrun) · MCP: `npx fartrun@latest install`*