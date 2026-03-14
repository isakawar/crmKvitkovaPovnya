import csv
import io
import re
import logging
import datetime

from app.extensions import db
from app.models import Client, Order, Delivery

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------

def normalize_phone(raw: str) -> str | None:
    """
    Strips spaces/dashes/brackets, normalizes to +380XXXXXXXXX format.
    Returns None if result doesn't look like a valid UA phone.
    """
    if not raw:
        return None
    # Take only first line (some cells have multiple phones separated by newline)
    raw = raw.split('\n')[0].strip()
    # Strip anything in parentheses
    raw = re.sub(r'\([^)]*\)', '', raw)
    # Keep only digits and leading +
    digits_only = re.sub(r'[^\d+]', '', raw).strip()
    if not digits_only:
        return None
    # Normalize to +380...
    if digits_only.startswith('+380') and len(digits_only) == 13:
        return digits_only
    if digits_only.startswith('380') and len(digits_only) == 12:
        return '+' + digits_only
    if digits_only.startswith('0') and len(digits_only) == 10:
        return '+38' + digits_only
    # Probably not a valid phone
    return None


def _is_phone_string(s: str) -> bool:
    """Returns True if the string looks like a phone number."""
    # Strip parenthetical notes and check remaining part
    cleaned = re.sub(r'\([^)]*\)', '', s).strip()
    digits = re.sub(r'[\s\-+]', '', cleaned)
    return bool(re.match(r'^0\d{8,9}$|^\+?380\d{9}$', digits))


# ---------------------------------------------------------------------------
# "Клієнт" field parser
# ---------------------------------------------------------------------------

def parse_client_field(raw: str) -> dict:
    """
    Returns dict with keys: instagram, phone, telegram (all may be None).
    The 'instagram' field is also used as the unique display identifier in the CRM.

    Rules:
      - starts with @          → telegram handle, store raw as instagram identifier too
      - matches phone pattern  → phone field; instagram = cleaned digits
      - contains (телеграм)    → telegram; instagram = name without suffix
      - contains (вотцап)/(вотсап) → phone; instagram = cleaned
      - plain text             → instagram
    """
    raw = raw.strip()
    if not raw:
        return {'instagram': None, 'phone': None, 'telegram': None}

    result = {'instagram': None, 'phone': None, 'telegram': None}

    # 1. Starts with @ → Telegram (possibly followed by name in parentheses)
    if raw.startswith('@'):
        # e.g. "@Old_sema (Ігор Стародуб)"
        handle = re.split(r'\s', raw)[0]  # take first word
        result['telegram'] = handle
        result['instagram'] = handle  # use as display id
        return result

    # 2. Contains (телеграм) suffix
    if '(телеграм' in raw.lower() or '(telegram' in raw.lower():
        name = re.sub(r'\(телеграм[^)]*\)', '', raw, flags=re.IGNORECASE).strip()
        name = re.sub(r'\(telegram[^)]*\)', '', name, flags=re.IGNORECASE).strip()
        result['telegram'] = name
        result['instagram'] = name
        return result

    # 3. Phone number (possibly followed by (вотцап) or (вотсап))
    #    Also handles "0 50 442 57 57(телеграм Anatoliy)" already caught above
    #    Check for phone-like starts: digit or +
    raw_no_parens = re.sub(r'\([^)]*\)', '', raw).strip()
    if _is_phone_string(raw_no_parens):
        normalized = normalize_phone(raw_no_parens)
        if normalized:
            result['phone'] = normalized
            result['instagram'] = normalized  # use normalized phone as identifier
            return result

    # 4. Everything else → Instagram
    result['instagram'] = raw
    return result


# ---------------------------------------------------------------------------
# Time range parser
# ---------------------------------------------------------------------------

def parse_time_range(raw: str) -> tuple[str | None, str | None]:
    """Parses '8:00-11:00' → ('08:00', '11:00'). Returns (None, None) on failure."""
    if not raw or not raw.strip():
        return None, None
    match = re.search(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', raw)
    if match:
        def pad(t):
            h, m = t.split(':')
            return f'{int(h):02d}:{m}'
        return pad(match.group(1)), pad(match.group(2))
    return None, None


# ---------------------------------------------------------------------------
# Address parser
# ---------------------------------------------------------------------------

# Keywords that indicate the "detail" part of an address (apt, floor, entrance...)
_COMMENT_TRIGGER = re.compile(
    r'(?<!\w)('
    r'кв[\.\s№]|квартира|кВ[\.\s№]'
    r'|поверх'
    r'|під\'їзд|підʼїзд|підїзд|під\s*їзд|парадне'
    r'|секція'
    r'|корпус'
    r'|ЖК\s'
    r'|домофон'
    r')',
    re.IGNORECASE | re.UNICODE,
)

# City prefix patterns
_CITY_PREFIX = re.compile(r'^м\.?\s*([А-ЯІЇЄҐа-яіїєґ\'\-]+)\s*,\s*', re.UNICODE)

KNOWN_CITIES = [
    'Київ', 'Бориспіль', 'Бровари', 'Ірпінь', 'Буча', 'Вишгород',
    'Обухів', 'Фастів', 'Васильків', 'Біла Церква', 'Вінниця',
    'Дніпро', 'Харків', 'Одеса', 'Львів', 'Чернівці', 'Запоріжжя',
    'Маріуполь', 'Кривий Ріг', 'Миколаїв', 'Херсон', 'Черкаси',
    'Полтава', 'Хмельницький', 'Суми', 'Житомир', 'Рівне',
    'Луцьк', 'Тернопіль', 'Ужгород', 'Івано-Франківськ',
    'Кропивницький', 'Краматорськ', 'Снігурівка', 'Буча',
    'Марганець', 'Винники', 'Круглик', 'Ходосівка', 'Славське',
    'Сеньківка', 'Бориспіль', 'Софіївська Борщагівка',
    '软іївська Боршагівка',
]


def _detect_method(raw: str) -> tuple[str, bool]:
    """Returns (delivery_method, is_pickup)."""
    lower = raw.lower() if raw else ''
    if 'нова пошта' in lower or re.search(r'\bнп\b', lower):
        return 'nova_poshta', False
    if 'самовивіз' in lower:
        return 'courier', True
    return 'courier', False


def parse_address(raw: str) -> dict:
    """
    Splits a free-form CSV address string into structured fields.

    Returns:
        city            – extracted or default "Київ"
        street          – street name + building number
        address_comment – apartment, floor, entrance, notes, etc.
        delivery_method – 'courier' | 'nova_poshta'
        is_pickup       – bool
    """
    if not raw or not raw.strip():
        return {
            'city': 'Київ', 'street': '', 'address_comment': '',
            'delivery_method': 'courier', 'is_pickup': False,
        }

    delivery_method, is_pickup = _detect_method(raw)

    # Normalize: collapse newlines to ", " and multiple spaces
    text = re.sub(r'[\r\n]+', ', ', raw).strip()
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()

    # Nova Poshta / pickup – keep everything in street, no splitting
    if delivery_method == 'nova_poshta' or is_pickup:
        return {
            'city': 'Київ', 'street': text, 'address_comment': '',
            'delivery_method': delivery_method, 'is_pickup': is_pickup,
        }

    # --- Extract city ---
    city = 'Київ'

    # Pattern: "м. Київ, ..." or "м.Київ, ..."
    m = _CITY_PREFIX.match(text)
    if m:
        city = m.group(1)
        text = text[m.end():].strip().lstrip(',').strip()
    else:
        # Try known cities at the very beginning "Київ, ..." or "Бориспіль, ..."
        for known in KNOWN_CITIES:
            pattern = rf'^{re.escape(known)}\s*,\s*'
            mc = re.match(pattern, text, re.IGNORECASE)
            if mc:
                city = known
                text = text[mc.end():].strip()
                break

    # --- Split street vs address_comment ---
    # Find first occurrence of a "detail" keyword
    m = _COMMENT_TRIGGER.search(text)
    if m:
        before = text[:m.start()]
        last_comma = before.rfind(',')
        if last_comma >= 0:
            street_part = before[:last_comma].strip()
            # Anything between the last comma and keyword belongs with the comment
            extra = before[last_comma + 1:].strip()
            comment_part = ((extra + ' ') if extra else '') + text[m.start():].strip()
        else:
            street_part = before.strip().rstrip('.').strip()
            comment_part = text[m.start():].strip()
    else:
        street_part = text
        comment_part = ''

    return {
        'city': city,
        'street': street_part,
        'address_comment': comment_part,
        'delivery_method': delivery_method,
        'is_pickup': is_pickup,
    }


# Keep backward-compat alias used in build_preview_row
def detect_delivery_method(address: str) -> tuple[str, bool]:
    return _detect_method(address)


# ---------------------------------------------------------------------------
# Delivery type normalization
# ---------------------------------------------------------------------------

DELIVERY_TYPE_MAP = {
    'weekly': 'Weekly',
    'monthly': 'Monthly',
    'bi-weekly': 'Bi-weekly',
    'one-time': 'One-time',
    'one_time': 'One-time',
    'test': 'Test',
}


def normalize_delivery_type(raw: str) -> str:
    if not raw:
        return 'One-time'
    return DELIVERY_TYPE_MAP.get(raw.lower().strip(), raw.strip())


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    'Клієнт', 'Тип підписки', 'Розмір', 'Коробка/Букет',
    'Тип композиції', 'Загальні побажання клієнта', 'Коментарі',
    'Час доставки', 'Імʼя отримувача', 'Адреса', 'Телефон отримувача'
]


def parse_csv_rows(file_stream) -> tuple[list[dict], str | None]:
    """
    Parse CSV file stream → list of raw row dicts.
    Returns (rows, error_message).
    """
    try:
        content = file_stream.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')  # handle BOM
        reader = csv.DictReader(io.StringIO(content))
        rows = []
        for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
            client_raw = row.get('Клієнт', '').strip()
            # Skip empty rows or #N/A rows
            if not client_raw or client_raw == '#N/A':
                continue
            rows.append({
                'row_num': i,
                'raw_client': client_raw,
                'delivery_type_raw': row.get('Тип підписки', '').strip(),
                'size': row.get('Розмір', '').strip(),
                'bouquet': row.get('Коробка/Букет', '').strip(),
                'composition_type': row.get('Тип композиції', '').strip(),
                'preferences_raw': row.get('Загальні побажання клієнта', '').strip(),
                'comment_raw': row.get('Коментарі', '').strip(),
                'time_raw': row.get('Час доставки', '').strip(),
                'recipient_name': row.get('Імʼя отримувача', '').strip(),
                'address_raw': row.get('Адреса', '').strip(),
                'recipient_phone_raw': row.get('Телефон отримувача', '').strip(),
            })
        return rows, None
    except Exception as e:
        logger.error(f'CSV parse error: {e}')
        return [], f'Помилка читання CSV: {e}'


# ---------------------------------------------------------------------------
# Strip numeric/duplicate suffixes from client names for dedup
# e.g. "chrisfetisova 1" → "chrisfetisova", "lanatremtii(2)" → "lanatremtii"
# ---------------------------------------------------------------------------

def _strip_suffix(name: str) -> str:
    if not name:
        return name
    # Remove trailing " (N)" or " N" or "(N)" suffixes
    cleaned = re.sub(r'\s*\(\d+\)\s*$', '', name).strip()
    cleaned = re.sub(r'\s+\d+\s*$', '', cleaned).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Find existing client
# ---------------------------------------------------------------------------

def find_existing_client(instagram=None, phone=None, telegram=None) -> Client | None:
    """
    Try to find an existing client by any of the three identifiers.
    Also checks stripped suffix variants.
    """
    if instagram:
        # Try exact match
        c = Client.query.filter_by(instagram=instagram).first()
        if c:
            return c
        # Try stripped suffix
        stripped = _strip_suffix(instagram)
        if stripped != instagram:
            c = Client.query.filter_by(instagram=stripped).first()
            if c:
                return c
        # Try phone-as-instagram
    if phone:
        c = Client.query.filter_by(phone=phone).first()
        if c:
            return c
        # Also try matching instagram that looks like this phone
        c = Client.query.filter_by(instagram=phone).first()
        if c:
            return c
    if telegram:
        c = Client.query.filter_by(telegram=telegram).first()
        if c:
            return c
        # Also try instagram = telegram handle
        c = Client.query.filter_by(instagram=telegram).first()
        if c:
            return c
    return None


# ---------------------------------------------------------------------------
# Build row preview dict (enriched with parsed + client status)
# ---------------------------------------------------------------------------

def build_preview_row(raw: dict) -> dict:
    """Enrich a raw row dict with parsed fields and client lookup."""
    client_info = parse_client_field(raw['raw_client'])
    addr = parse_address(raw['address_raw'])
    time_from, time_to = parse_time_range(raw['time_raw'])
    recipient_phone = normalize_phone(raw['recipient_phone_raw'])
    delivery_type = normalize_delivery_type(raw['delivery_type_raw'])

    composition_type = raw['composition_type'] if raw['composition_type'] and raw['composition_type'] != '#N/A' else None
    bouquet_type = raw['bouquet'] if raw['bouquet'] and raw['bouquet'] != '#N/A' else None
    preferences = raw['preferences_raw'] if raw['preferences_raw'] and raw['preferences_raw'] != '#N/A' else None
    comment = raw['comment_raw'] if raw['comment_raw'] and raw['comment_raw'] != '#N/A' else None

    # Determine size
    size = raw['size'] if raw['size'] and raw['size'] != '#N/A' else 'M'

    existing = find_existing_client(
        instagram=client_info['instagram'],
        phone=client_info['phone'],
        telegram=client_info['telegram'],
    )

    # Warnings
    warnings = []
    if not client_info['instagram']:
        warnings.append('Не вдалося визначити ідентифікатор клієнта')
    if not recipient_phone and raw['recipient_phone_raw']:
        warnings.append(f'Не вдалося нормалізувати телефон: {raw["recipient_phone_raw"][:30]}')

    return {
        'row_num': raw['row_num'],
        'raw_client': raw['raw_client'],
        # Parsed client fields
        'instagram': client_info['instagram'],
        'phone': client_info['phone'],
        'telegram': client_info['telegram'],
        'client_type': (
            'telegram' if client_info['telegram'] else
            'phone' if (client_info['phone'] and client_info['instagram'] == client_info['phone']) else
            'instagram'
        ),
        # Existing client info
        'existing_client_id': existing.id if existing else None,
        'client_status': 'exists' if existing else 'new',
        # Order fields
        'delivery_type': delivery_type,
        'delivery_type_raw': raw['delivery_type_raw'],
        'size': size,
        'bouquet': raw['bouquet'],
        'recipient_name': raw['recipient_name'] if raw['recipient_name'] != '#N/A' else '',
        'recipient_phone': recipient_phone,
        'city': addr['city'],
        'street': addr['street'],
        'address_comment': addr['address_comment'],
        'address': raw['address_raw'] if raw['address_raw'] != '#N/A' else '',
        'delivery_method': addr['delivery_method'],
        'is_pickup': addr['is_pickup'],
        'time_from': time_from,
        'time_to': time_to,
        'bouquet_type': bouquet_type,
        'composition_type': composition_type,
        'preferences': preferences,
        'comment': comment,
        'warnings': warnings,
    }


def preview_import(file_stream) -> tuple[list[dict], str | None]:
    """Parse CSV and build enriched preview rows. Returns (rows, error)."""
    raw_rows, error = parse_csv_rows(file_stream)
    if error:
        return [], error
    preview_rows = [build_preview_row(r) for r in raw_rows]
    return preview_rows, None


# ---------------------------------------------------------------------------
# Execute import
# ---------------------------------------------------------------------------

def execute_import(preview_rows: list[dict], first_delivery_date_str: str, delivery_day: str) -> dict:
    """
    For each preview row:
      1. Find or create Client
      2. Create Order + Deliveries via order_service logic
    Returns summary dict.
    """
    from app.services.order_service import create_order_and_deliveries

    try:
        first_delivery_date = datetime.datetime.strptime(first_delivery_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        first_delivery_date = datetime.date.today()

    created_clients = 0
    existing_clients = 0
    created_orders = 0
    errors = []

    for row in preview_rows:
        try:
            # 1. Find or create client
            existing = find_existing_client(
                instagram=row['instagram'],
                phone=row['phone'],
                telegram=row['telegram'],
            )

            if existing:
                client = existing
                existing_clients += 1
            else:
                if not row['instagram']:
                    errors.append(f'Рядок {row["row_num"]}: неможливо визначити ідентифікатор клієнта, пропущено')
                    continue

                # Build safe instagram identifier (strip suffixes for client creation)
                instagram_id = _strip_suffix(row['instagram'])

                # Check if stripped version already exists
                existing_stripped = Client.query.filter_by(instagram=instagram_id).first()
                if existing_stripped:
                    client = existing_stripped
                    existing_clients += 1
                else:
                    client = Client(
                        instagram=instagram_id,
                        phone=row['phone'],
                        telegram=row['telegram'],
                    )
                    db.session.add(client)
                    db.session.flush()  # get client.id without full commit
                    created_clients += 1

            # 2. Build form dict for create_order_and_deliveries
            form = {
                'recipient_name': row['recipient_name'] or '',
                'recipient_phone': row['recipient_phone'] or '',
                'recipient_social': '',
                'city': row.get('city') or 'Київ',
                'street': row.get('street') or row.get('address') or '',
                'address_comment': row.get('address_comment') or '',
                'building_number': '',
                'floor': '',
                'entrance': '',
                'is_pickup': 'on' if row['is_pickup'] else '',
                'delivery_type': row['delivery_type'],
                'size': row['size'],
                'custom_amount': '',
                'first_delivery_date': first_delivery_date.strftime('%Y-%m-%d'),
                'delivery_day': delivery_day,
                'time_from': row['time_from'] or '',
                'time_to': row['time_to'] or '',
                'comment': row['comment'] or '',
                'preferences': row['preferences'] or '',
                'bouquet_type': row.get('bouquet_type') or '',
                'composition_type': row.get('composition_type') or '',
                'for_whom': '',
                'delivery_method': row['delivery_method'],
            }

            create_order_and_deliveries(client, form)
            created_orders += 1

        except Exception as e:
            logger.error(f'Import error row {row["row_num"]}: {e}', exc_info=True)
            errors.append(f'Рядок {row["row_num"]} ({row["raw_client"]}): {e}')
            db.session.rollback()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f'Commit error: {e}', exc_info=True)
        errors.append(f'Помилка збереження в БД: {e}')

    return {
        'created_clients': created_clients,
        'existing_clients': existing_clients,
        'created_orders': created_orders,
        'errors': errors,
    }
