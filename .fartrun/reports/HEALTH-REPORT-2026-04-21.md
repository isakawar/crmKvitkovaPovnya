# Health Report: crmKvitkovaPovnya

Scanned: 2026-04-21 23:31
Total findings: 118 (actionable: 100)

🟡 medium: 68 | 🔵 low: 32 | ℹ️ info: 18

**Files:** 242
**Entry points:** package.json, run.py, .agents/skills/qa-expert/scripts/calculate_metrics.py

## Recommended action order

1. reduce tech debt (30 items)
2. extract duplicates (10 items)
3. modules (9 items)
4. remove dead code (8 items)
5. split large files (6 items)
6. remove unused imports (4 items)
7. unfinished (1 items)

---

## 🟡 MEDIUM (68)

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

- [ ] **Circular: app/blueprints/orders/__init__.py ↔ app/blueprints/orders/deliveries.py**
  - app/blueprints/orders/__init__.py imports app/blueprints/orders/deliveries.py, and app/blueprints/orders/deliveries.py imports app/blueprints/orders/__init__.py.
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

- [ ] **Circular: app/blueprints/orders/__init__.py ↔ app/blueprints/orders/orders.py**
  - app/blueprints/orders/__init__.py imports app/blueprints/orders/orders.py, and app/blueprints/orders/orders.py imports app/blueprints/orders/__init__.py.
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

- [ ] **Circular: app/blueprints/orders/__init__.py ↔ app/blueprints/orders/route_distribute.py**
  - app/blueprints/orders/__init__.py imports app/blueprints/orders/route_distribute.py, and app/blueprints/orders/route_distribute.py imports app/blueprints/orders/__init__.py.
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

- [ ] **Circular: app/blueprints/orders/__init__.py ↔ app/blueprints/orders/route_generator.py**
  - app/blueprints/orders/__init__.py imports app/blueprints/orders/route_generator.py, and app/blueprints/orders/route_generator.py imports app/blueprints/orders/__init__.py.
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

- [ ] **Circular: app/blueprints/orders/__init__.py ↔ app/blueprints/orders/route_saver.py**
  - app/blueprints/orders/__init__.py imports app/blueprints/orders/route_saver.py, and app/blueprints/orders/route_saver.py imports app/blueprints/orders/__init__.py.
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

> Monster files are hard for AI to work with — context window limits mean Claude can't see the whole file at once. Split to improve AI-assisted development.

- [ ] **Monster: app/telegram_bot/handlers.py**
  - app/telegram_bot/handlers.py — 938 lines, 31 functions.
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
  - app/services/ai_agent_service.py — 807 lines, 18 functions.

- [ ] **Monster: app/static/js/clients.js**
  - app/static/js/clients.js — 601 lines, 53 functions.

- [ ] **Monster: app/blueprints/orders/orders.py**
  - app/blueprints/orders/orders.py — 541 lines, 14 functions.

- [ ] **Monster: app/services/csv_import_service.py**
  - app/services/csv_import_service.py — 521 lines, 16 functions.

- [ ] **Monster: app/services/subscription_service.py**
  - app/services/subscription_service.py — 521 lines, 16 functions.

> Unused imports add noise, slow down IDE indexing, and can mask real dependencies. Safe to remove after verifying they're not side-effect imports.

- [ ] **Unused: os**
  - os imported in .agents/skills/qa-expert/scripts/init_qa_project.py:15 but never used.

- [ ] **Unused: os**
  - os imported in .claude/skills/qa-expert/scripts/init_qa_project.py:15 but never used.

- [ ] **Unused: os**
  - os imported in scripts/database_backup.py:6 but never used.

- [ ] **Unused: asyncio**
  - asyncio imported in scripts/run_telegram_bot.py:9 but never used.

> Dead code confuses AI assistants and developers. If a function isn't called, it's either forgotten or accessed via framework magic — verify before deleting.

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

- [ ] **Unused function: initCityAutocomplete**
  - initCityAutocomplete() in app/static/js/city_autocomplete.js — defined but never called anywhere in the project.

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

- [ ] **Duplicate: app/blueprints/orders/route_distribute.py ↔ app/blueprints/orders/route_saver.py (14 lines)**
  - 14 duplicate lines: app/blueprints/orders/route_distribute.py:172 and app/blueprints/orders/route_saver.py:122.

- [ ] **Duplicate: app/models/order.py ↔ app/models/subscription.py (13 lines)**
  - 13 duplicate lines: app/models/order.py:13 and app/models/subscription.py:20.

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

- [ ] **route_generator_job_status() — 1 params without types, no return type**
  - route_generator_job_status() in app/blueprints/orders/route_generator.py:216 — 1 params without types, no return type.

- [ ] **order_edit() — 1 params without types, no return type**
  - order_edit() in app/blueprints/orders/orders.py:293 — 1 params without types, no return type.

- [ ] **order_dependencies() — 1 params without types, no return type**
  - order_dependencies() in app/blueprints/orders/orders.py:359 — 1 params without types, no return type.

- [ ] **order_delete() — 1 params without types, no return type**
  - order_delete() in app/blueprints/orders/orders.py:383 — 1 params without types, no return type.

- [ ] **update_order_bouquet_type() — 1 params without types, no return type**
  - update_order_bouquet_type() in app/blueprints/orders/orders.py:391 — 1 params without types, no return type.

- [ ] **Unfinished work: 25 uncommitted files**
  - You have 25 uncommitted files.


## 🔵 LOW (32)

- [ ] **Orphan: migrations/versions/add_test_delivery_type.py**
  - migrations/versions/add_test_delivery_type.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/initial_postgresql_migration.py**
  - migrations/versions/initial_postgresql_migration.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/add_route_cache.py**
  - migrations/versions/add_route_cache.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/add_recipient_phones_table.py**
  - migrations/versions/add_recipient_phones_table.py — nobody imports it, not an entry point.

- [ ] **Orphan: migrations/versions/add_subscription_renewal_reminder.py**
  - migrations/versions/add_subscription_renewal_reminder.py — nobody imports it, not an entry point.

> Bare except/empty catch blocks silently swallow errors. When something breaks, you won't know what or where. Log or handle specifically.

- [ ] **except_pass: app/services/csv_import_service.py:383**
  - app/services/csv_import_service.py:383 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/csv_import_service.py:413**
  - app/services/csv_import_service.py:413 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/ai_agent_service.py:320**
  - app/services/ai_agent_service.py:320 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/ai_agent_service.py:846**
  - app/services/ai_agent_service.py:846 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/order_service.py:129**
  - app/services/order_service.py:129 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/order_service.py:135**
  - app/services/order_service.py:135 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/delivery_service.py:146**
  - app/services/delivery_service.py:146 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/route_optimizer_service.py:84**
  - app/services/route_optimizer_service.py:84 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/route_optimizer_service.py:119**
  - app/services/route_optimizer_service.py:119 — except with only 'pass' — silently swallows errors.

- [ ] **except_pass: app/services/route_optimizer_service.py:224**
  - app/services/route_optimizer_service.py:224 — except with only 'pass' — silently swallows errors.

> Hardcoded values (URLs, ports, keys) break when environments change. Extract to config/env vars.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:19**
  - app/blueprints/routes/routes.py:19 — https://api.telegram.org/bot{bot_token}/sendMessage.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:34**
  - app/blueprints/routes/routes.py:34 — https://api.telegram.org/bot{bot_token}/editMessageText.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:259**
  - app/blueprints/routes/routes.py:259 — https://www.google.com/maps/dir/.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:329**
  - app/blueprints/routes/routes.py:329 — https://www.google.com/maps/dir/.

- [ ] **Hardcoded url: app/blueprints/routes/routes.py:331**
  - app/blueprints/routes/routes.py:331 — https://tinyurl.com/api-create.php.

- [ ] **Hardcoded url: app/config.py:26**
  - app/config.py:26 — https://openrouter.ai/api/v1.

- [ ] **Hardcoded url: app/config.py:54**
  - app/config.py:54 — https://openrouter.ai/api/v1.

- [ ] **Hardcoded url: app/telegram_bot/handlers.py:1106**
  - app/telegram_bot/handlers.py:1106 — https://www.google.com/maps/dir/.

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

- [ ] **Big commit: ec011e3 (1455 lines)**
  - Commit 'refactor(orders): remove obsolete routes.py' changed 1455 lines.

- [ ] **Big commit: fee5a08 (1497 lines)**
  - Commit 'refactor(orders): split routes.py into 5 focused modules' changed 1497 lines.

- [ ] **Big commit: 13b18a2 (626 lines)**
  - Commit 'Save Point: before cleanup' changed 626 lines.

- [ ] **README incomplete: missing installation instructions**
  - README exists (254 lines) but missing: installation instructions.

- [ ] **Unused in requirements.txt: apscheduler, flask_wtf, gunicorn**
  - In requirements.txt but not imported: apscheduler, flask_wtf, gunicorn, psycopg2_binary, pytest.


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

- **Project Map**: In your project: 242 files. Most common: .py (128). This is just context — now you know what's inside.
- **Entry Points**: Entry point = the file where everything starts. Like doors to a building. You have 9.
- **Hub: app/extensions.py**: app/extensions.py is imported by 45 files. This is your most important module. Break it — break everything.
- **Hub: app/models/__init__.py**: app/models/__init__.py is imported by 29 files. This is your most important module. Break it — break everything.
- **Hub: app/models/delivery_route.py**: app/models/delivery_route.py is imported by 17 files. This is your most important module. Break it — break everything.
- **Dependencies up to date**: All checked dependencies are on latest versions.
- **Tests: 15 files (pytest)**: 15 test files found (15 Python). Framework: pytest.
- **Session: 15 commits, ~59 files touched**: Last 8 hours: 15 commits, ~59 files modified.
- **Before building — search first**: Before writing a new feature: google it. Check GitHub repos, PyPI, npm. Someone probably already built what you need. Don't reinvent the wheel — steal the wheel.
- **Git status: 1 staged (ready to commit), 21 modified (changed but not staged), 3 deleted (not staged)**: Working tree: 1 staged (ready to commit), 21 modified (changed but not staged), 3 deleted (not staged). Staged files are ready for commit. Modified files need 'git add' before commit. Deleted files need 'git add' (or 'git restore') to stage the deletion. 
- **3 unmerged branches**: Branches not merged: feat/billing, feat/draft-subscriptions-on-orders, redisigne/ui. Merge or delete them to keep things clean.
- **Git commands you need right now**: git add <file> — stage your changes for commit | git commit -m 'description' — save staged changes | git stash — temporarily hide changes, work on something else
- **UI Element Dictionary available**: Frontend project detected. Can't explain to AI which button to change? Open the UI Dictionary — 20 elements with names, pictures, and example prompts.
- **Unknown packages: flask_sqlalchemy, flask_wtf, flask_migrate**: AI might not know these packages: flask_sqlalchemy (pypi), flask_wtf (pypi), flask_migrate (pypi), python_dotenv (pypi), python_telegram_bot (pypi) (+3 more). Fetch their docs so AI understands your stack.
### LLM Context Summary

Copy this to give AI context about your project:
# Project: crmKvitkovaPovnya

**Stack:** Python, JavaScript/TypeScript, Docker

**Size:** 242 files, 73 dirs

**Entry points:**
- `package.json` — Node.js project config (scripts: dev)
- `run.py` — Python main module
- `.agents/skills/qa-expert/scripts/calculate_metrics.py` — Python script with __main__ guard
- `.agents/skills/qa-expert/scripts/init_qa_project.py` — Python script with __main__ guard
- `.claude/skills/qa-expert/scripts/calculate_metrics.py` — Python script with __main__ guard

**Key modules:**
- `app/extensions.py` (imported by 45 files)
- `app/models/__init__.py` (imported by 29 files)
- `app/models/delivery_route.py` (imported by 17 files)
- `app/models/subscription.py` (imported by 14 files)
- `app/models/delivery.py` (imported by 10 files)

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