# Testing Patterns

**Analysis Date:** 2026-04-02

## Test Framework

**Runner:**
- pytest 
- Configuration: `tests/conftest.py` (shared fixture definitions)
- No `pytest.ini` or `setup.cfg`; pytest auto-discovers `tests/` directory

**Assertion Library:**
- pytest assertions (built-in `assert` statements)

**Run Commands:**
```bash
pytest                          # Run all tests
pytest tests/test_orders.py     # Run specific test file
pytest -v                       # Verbose output
pytest --tb=short              # Shorter traceback format
```

## Test File Organization

**Location:**
- Tests co-located in `tests/unit/` directory parallel to `app/` structure
- Test file names: `test_{entity}_service.py` (e.g., `test_order_service.py`)
- Test modules paired with service modules: `app/services/order_service.py` → `tests/unit/test_order_service.py`

**Naming:**
- Test files: `test_*.py` (pytest convention)
- Test functions: `test_{functionality}_{expected_outcome}()` (e.g., `test_create_client_ok()`, `test_create_order_delivery_has_no_street()`)
- Descriptive names replace docstrings; clarity through naming

**Structure:**
```
tests/
├── conftest.py                 # Shared fixtures (app, session, client_fixture, etc.)
├── unit/                       # Unit tests
│   ├── test_order_service.py
│   ├── test_client_service.py
│   ├── test_delivery_service.py
│   ├── test_subscription_service.py
│   └── test_certificate_model.py
└── qa/tests/                   # QA/integration tests (separate structure)
```

## Test Structure

**Suite Organization:**
- Fixture-based: `conftest.py` defines reusable fixtures (`app`, `session`, `client_fixture`, `courier_fixture`, `subscription_fixture`)
- Flat organization: no `TestClass` pattern; standalone test functions
- Helper functions prefixed with underscore: `_make_client()`, `_base_form()` defined within test modules
- Section comments using `# ── Section Name ──` format to group related tests

**Example from `tests/unit/test_order_service.py`:**
```python
# ── Helpers ───────────────────────────────────────────────────────────────────

class FakeForm(dict):
    """Minimal dict-like object that also has .getlist() for multi-value fields."""
    def getlist(self, key):
        val = self.get(key, [])
        return val if isinstance(val, list) else [val]

def _base_form(**overrides):
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({...})
    form.update(overrides)
    return form

# ── get_or_create_client ──────────────────────────────────────────────────────

def test_get_or_create_client_unknown_instagram_returns_none(session):
    ...
```

**Patterns:**
- Setup: Create fixture dependencies or use built-in fixtures (`session`, `app`)
- Action: Call function under test with prepared data
- Assertion: Single or few focused assertions per test
- Teardown: Automatic via fixture (no explicit cleanup needed due to SQLite in-memory DB)

## Mocking

**Framework:** 
- No explicit mocking library (pytest-mock, unittest.mock) currently used
- Manual stubs where needed (e.g., `FakeForm` class in `test_order_service.py`)

**Patterns:**
- Form-like objects created as simple dict subclasses: `FakeForm` implements `.getlist()` for multi-value field testing
- Real database state used for relational tests (no mock models)
- Late-import mocking: Import real classes, create instances with controlled state

**Example fake form from `tests/unit/test_order_service.py`:**
```python
class FakeForm(dict):
    """Minimal dict-like object that also has .getlist() for multi-value fields."""
    def getlist(self, key):
        val = self.get(key, [])
        return val if isinstance(val, list) else [val]

def _base_form(**overrides):
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = FakeForm({
        'recipient_name': 'Тест Отримувач',
        'recipient_phone': '+380991234567',
        'first_delivery_date': tomorrow,
        'city': 'Київ',
        'street': 'Хрещатик 1',
        'size': 'M',
        'for_whom': 'Дружина',
        'delivery_method': 'courier',
        'additional_phones': [],
    })
    form.update(overrides)
    return form
```

**What to Mock:**
- External APIs not tested (route optimizer, Telegram bot would be mocked in integration tests)
- Time-dependent functions tested with fixed dates (see `test_subscription_service.py` line 34: `_MONDAY = datetime.date(2026, 3, 30)`)

**What NOT to Mock:**
- Database: use real SQLite in-memory instance for realistic relationship testing
- Models: instantiate real ORM models to catch schema mismatches
- Service functions: call real service functions, mock only external dependencies

## Fixtures and Factories

**Test Data:**
- Fixtures defined in `tests/conftest.py` for cross-file reuse
- Helper factories prefixed with underscore within test modules for local data

**Built-in Fixtures from conftest.py:**
```python
@pytest.fixture
def app():
    """Flask app with fresh in-memory SQLite DB per test."""
    flask_app = create_app(TestingConfig)
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['LOGIN_DISABLED'] = True
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def session(app):
    """Return the active db.session (already inside the app context)."""
    return _db.session

@pytest.fixture
def client_fixture(session):
    c = Client(instagram='test_user')
    session.add(c)
    session.commit()
    return c

@pytest.fixture
def courier_fixture(session):
    c = Courier(name='Іван', phone='+380991234567', deliveries_count=0)
    session.add(c)
    session.commit()
    return c

@pytest.fixture
def subscription_fixture(client_fixture, session):
    sub = Subscription(
        client_id=client_fixture.id,
        type='Weekly',
        status='active',
        delivery_day='ПН',
        recipient_name='Отримувач',
        recipient_phone='+380991234567',
        city='Київ',
        street='Хрещатик 1',
        size='M',
        for_whom='Дружина',
    )
    session.add(sub)
    session.commit()
    return sub

@pytest.fixture
def order_with_delivery(client_fixture, subscription_fixture, session):
    # Creates Order + Delivery pair with realistic data
    ...
    return order, delivery
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Test-local helpers: defined as functions within test modules (prefixed `_`)
- Parametrized test data: defined as constants or passed via `@pytest.mark.parametrize`

**Example from `tests/unit/test_client_service.py`:**
```python
def _make_client(session, instagram, phone=None, telegram=None):
    """Helper factory for creating test clients."""
    c = Client(instagram=instagram, phone=phone, telegram=telegram)
    session.add(c)
    session.commit()
    return c
```

## Coverage

**Requirements:** 
- No coverage tool configured or enforced
- Manual review of critical paths (services, models)

**View Coverage:**
```bash
# Coverage not set up; use pytest with coverage plugin:
pytest --cov=app --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- **Scope:** Service functions, model methods, business logic
- **Approach:** Isolated function calls with fixture-prepared data, no HTTP layer
- **Location:** `tests/unit/`
- **Example:** `test_create_client_ok()` in `tests/unit/test_client_service.py` — tests client creation, normalization, and duplicate detection

**Integration Tests:**
- **Scope:** Not explicitly organized, but some unit tests use DB relationships
- **Approach:** Real database with ORM relationships preserved (e.g., `order_with_delivery` fixture tests Order-Delivery link)
- **Location:** Tests in `unit/` that use multiple fixtures (`order_with_delivery`)

**E2E Tests:**
- **Framework:** Not used
- **Note:** Web routes tested manually or via QA structure in `tests/qa/`

## Common Patterns

**Async Testing:**
- Not applicable (Flask synchronous framework)

**Error Testing:**
```python
# Parametrized error cases:
@pytest.mark.parametrize('bad_phone', [
    '0991111111',        # missing +380 prefix
    '+38099111111',      # too short
    '+3809911111111',    # too long
    '+380991111111a',    # contains letter
    '380991111111',      # no leading +
])
def test_create_client_invalid_phone(session, bad_phone):
    client, err = create_client(f'user_{bad_phone}', phone=bad_phone)
    assert client is None
    assert err is not None
```

**Expected Failures (xfail):**
```python
@pytest.mark.xfail(reason='BUG-03: delivery_date in the past is not validated')
def test_create_order_rejects_past_delivery_date(session):
    """
    BUG-03: order_service.create_order_and_deliveries accepts past dates.
    This test documents the expected behaviour after the bug is fixed.
    """
    client = _make_client(session, 'past_date_client')
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    form = _base_form(first_delivery_date=yesterday)
    
    with pytest.raises((ValueError, Exception)):
        create_order_and_deliveries(client, form)
```

**Database Isolation:**
- Fresh SQLite in-memory DB per test function via fixture scope
- Tables created at test start, dropped at test end
- `session.flush()` used to get IDs without committing
- Relationships tested using real ORM lazy-loading

**Assertion Style:**
```python
# Single clear assertion per test is preferred
assert client is None
assert err is not None
assert isinstance(err, dict)
assert err['type'] == 'duplicate'
assert err['field'] == 'instagram'
assert 'client_id' in err
```

## Fixture Scope & Lifecycle

**Function Scope:**
- All fixtures use function scope (default)
- Each test gets fresh database: `_db.create_all()` before, `_db.drop_all()` after
- App and session recreated per test for full isolation
- This is slower but guarantees no cross-test pollution

**Fixture Dependencies:**
- `client_fixture` depends on `session`
- `subscription_fixture` depends on `client_fixture` + `session`
- `order_with_delivery` depends on `client_fixture`, `subscription_fixture`, `session`
- Pytest resolves dependency graph automatically

---

*Testing analysis: 2026-04-02*
