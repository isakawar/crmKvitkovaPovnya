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
    # 9 digits without leading 0 (e.g. '634365806' → '0634365806')
    if re.match(r'^[1-9]\d{8}$', digits_only):
        return '+380' + digits_only
    # Concatenated phones or names+phones — extract first valid 10-digit number
    # Only attempt if there are clearly more digits than a single phone (>13 with +)
    all_digits = re.sub(r'[^\d]', '', raw)
    if len(all_digits) > 13:
        m = re.search(r'0\d{9}', all_digits)
        if m:
            return '+38' + m.group(0)
    return None


def _is_phone_string(s: str) -> bool:
    """Returns True if the string looks like a phone number."""
    cleaned = re.sub(r'\([^)]*\)', '', s).strip()
    digits = re.sub(r'[\s\-+]', '', cleaned)
    # 0XXXXXXXXX, +380XXXXXXXXX, or 9-digit without leading 0 (e.g. 632113420)
    return bool(re.match(r'^0\d{8,9}$|^\+?380\d{9}$|^[1-9]\d{8}$', digits))


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

    # 1. Starts with @ → Telegram handle only (not instagram)
    if raw.startswith('@'):
        # e.g. "@Old_sema (Ігор Стародуб)"
        handle = re.split(r'\s', raw)[0]  # take first word
        result['telegram'] = handle
        result['instagram'] = handle
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
            result['instagram'] = normalized
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
# Strip numeric/duplicate suffixes from client names for dedup
# e.g. "chrisfetisova 1" → "chrisfetisova", "lanatremtii(2)" → "lanatremtii"
# ---------------------------------------------------------------------------

def _strip_suffix(name: str) -> str:
    if not name:
        return name
    # Don't strip from phone-like values — trailing digits are part of the number
    if _is_phone_string(name):
        return name
    # Remove trailing " (N)" or " N" or "(N)" suffixes from instagram handles
    # e.g. "chrisfetisova 1" → "chrisfetisova", "lanatremtii(2)" → "lanatremtii"
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
# Kvitkovapovnya 2026 operational CSV — new format
# ---------------------------------------------------------------------------

_DELIVERY_DAY_UA_MAP = {
    'субота': 'СБ', 'неділя': 'НД', 'понеділок': 'ПН',
    'вівторок': 'ВТ', 'середа': 'СР', 'четвер': 'ЧТ',
    "п'ятниця": 'ПТ', 'пʼятниця': 'ПТ', 'пятниця': 'ПТ',
}
_REVERSE_WEEKDAY_SHORT = {0: 'ПН', 1: 'ВТ', 2: 'СР', 3: 'ЧТ', 4: 'ПТ', 5: 'СБ', 6: 'НД'}


def parse_csv_rows_kvitkovapovnya(file_stream):
    """Parse rows from the Kvitkovapovnya 2026 CSV format."""
    import io
    import csv as csv_module

    content = file_stream.read()
    if isinstance(content, bytes):
        content = content.decode('utf-8-sig')

    reader = csv_module.DictReader(io.StringIO(content))
    rows = []
    for i, row in enumerate(reader, start=2):
        # Normalize keys
        normalized = {k.strip(): v.strip() if isinstance(v, str) else (v or '') for k, v in row.items()}

        raw_client = normalized.get('Name of clients', '').strip()
        if not raw_client:
            continue

        phones_raw = normalized.get('Номертелефону') or normalized.get('Номер телефону отримувача', '')
        phone_lines = [p.strip() for p in phones_raw.replace('\r', '').split('\n') if p.strip()]
        recipient_phone = normalize_phone(phone_lines[0]) if phone_lines else ''
        extra_phones = [normalize_phone(p) for p in phone_lines[1:] if normalize_phone(p)]

        rows.append({
            'row_num': i,
            'raw_client': raw_client,
            'recipient_name': normalized.get("Ім'я на кого доставка", '') or normalized.get('Імʼя на кого доставка', ''),
            'delivery_type_raw': normalized.get('Вид підписки', ''),
            'delivery_day_raw': normalized.get('Коли відправка', ''),
            'size': normalized.get('Розмір', ''),
            'city': normalized.get('Місто', ''),
            'address_raw': normalized.get('Адреса', ''),
            'address_comment_raw': normalized.get('Коментар до адреси', ''),
            'recipient_phone': recipient_phone,
            'recipient_phones_extra': extra_phones,
            'marketing_source': normalized.get('Звідки дізнались про нас', ''),
            'for_whom': normalized.get('Для кого', ''),
            'planned_date_raw': normalized.get('Планова доставка', ''),
            'delivery_number_raw': normalized.get('№ доставки', ''),
            'is_wedding_raw': normalized.get('Відмітка якщо весільна', ''),
            'discount_raw': normalized.get('Відсоток знижки', ''),
            'recipient_social_raw': normalized.get('Instagram / Telegram отримувача', ''),
            'preferences_raw': normalized.get('Побажання', ''),
        })
    return rows


def _parse_kvp_date(raw):
    """Parse dd.mm.yyyy date string, return date or None."""
    import datetime as dt
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ('%d.%m.%Y', '%d.%m.%y'):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _parse_kvp_discount(raw):
    """Parse discount like '10%' or '10', return int or None."""
    if not raw:
        return None
    raw = raw.strip().rstrip('%').strip()
    try:
        val = int(float(raw))
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def build_preview_row_kvitkovapovnya(raw):
    """Build a normalized preview row from raw parsed CSV data."""
    from app.services.subscription_service import SUBSCRIPTION_TYPES
    planned_date = None
    planned_date_raw = (raw.get('planned_date_raw') or '').strip()
    if planned_date_raw.lower() not in ('', 'доставки не плануються'):
        planned_date = _parse_kvp_date(planned_date_raw)

    delivery_number = None
    dn_raw = (raw.get('delivery_number_raw') or '').strip()
    if dn_raw and dn_raw.lower() not in ('', 'доставки не плануються'):
        try:
            delivery_number = int(dn_raw)
        except ValueError:
            pass

    delivery_day_raw = (raw.get('delivery_day_raw') or '').strip().lower()
    delivery_day = _DELIVERY_DAY_UA_MAP.get(delivery_day_raw, '')
    if not delivery_day and planned_date:
        delivery_day = _REVERSE_WEEKDAY_SHORT.get(planned_date.weekday(), 'ПН')

    discount = _parse_kvp_discount(raw.get('discount_raw'))
    is_wedding = bool((raw.get('is_wedding_raw') or '').strip()) or (raw.get('for_whom') or '').strip().lower() == 'весільна підписка'

    delivery_type_raw = (raw.get('delivery_type_raw') or '').strip()
    delivery_type_map = {
        'щотижнева': 'Weekly', 'weekly': 'Weekly',
        'щодвотижнева': 'Bi-weekly', 'bi-weekly': 'Bi-weekly', 'двотижнева': 'Bi-weekly',
        'щомісячна': 'Monthly', 'monthly': 'Monthly',
    }
    delivery_type = delivery_type_map.get(delivery_type_raw.lower(), delivery_type_raw)

    # Determine action
    if delivery_number is None:
        action = 'client_only'
    elif delivery_number == 0:
        action = 'one_time'
    elif delivery_number >= 5:
        action = 'subscription_followup'
    else:
        action = 'subscription'

    # If delivery_type is 'Test' or unknown, treat as client_only/one_time
    if delivery_type.lower() == 'test' or (delivery_type not in SUBSCRIPTION_TYPES and action in ('subscription', 'subscription_followup')):
        action = 'one_time' if delivery_number == 0 else 'client_only'

    size_raw = (raw.get('size') or '').strip()
    size_map = {'s': 'S', 'm': 'M', 'l': 'L', 'xl': 'XL', 'xxl': 'XXL'}
    size = size_map.get(size_raw.lower(), size_raw) or 'M'

    # Parse client identifier: @handle → telegram, plain text → instagram
    client_parsed = parse_client_field(_strip_suffix(raw['raw_client']))

    # Detect delivery method from address, comment, or city
    city_raw = (raw.get('city') or '').strip()
    address_raw = (raw.get('address_raw') or '').strip()
    addr_comment = (raw.get('address_comment_raw') or '').strip()

    comment_method, _ = _detect_method(addr_comment)
    addr_method, _ = _detect_method(address_raw)
    city_method, _ = _detect_method(city_raw)

    if comment_method == 'nova_poshta':
        # NP address is fully described in the comment — use it as the street address
        resolved_delivery_method = 'nova_poshta'
        address_raw = addr_comment
        addr_comment = ''
    elif addr_method == 'nova_poshta':
        resolved_delivery_method = 'nova_poshta'
    elif city_method == 'nova_poshta' and not address_raw:
        resolved_delivery_method = 'nova_poshta'
        address_raw = city_raw
    else:
        resolved_delivery_method = 'courier'

    city = city_raw or 'Київ'
    if city.startswith('#') or city.lower() in ('n/a', '#n/a'):
        city = 'Київ'

    warnings = []
    if action in ('one_time', 'subscription', 'subscription_followup') and not planned_date:
        warnings.append('Відсутня планова дата доставки')
    if action in ('subscription', 'subscription_followup') and not delivery_type:
        warnings.append('Відсутній тип підписки')

    return {
        'row_num': raw['row_num'],
        'raw_client': raw['raw_client'],
        'client_instagram': client_parsed['instagram'],
        'client_telegram': client_parsed['telegram'],
        'client_phone_id': client_parsed['phone'],
        'recipient_name': (raw.get('recipient_name') or '').strip(),
        'recipient_phone': raw.get('recipient_phone') or '',
        'recipient_phones_extra': raw.get('recipient_phones_extra') or [],
        'delivery_type': delivery_type,
        'delivery_day': delivery_day,
        'size': size,
        'city': city,
        'address_raw': address_raw,
        'address_comment': (raw.get('address_comment_raw') or '').strip(),
        'delivery_method': resolved_delivery_method,
        'for_whom': (raw.get('for_whom') or '').strip(),
        'marketing_source': (raw.get('marketing_source') or '').strip(),
        'planned_date': planned_date.strftime('%Y-%m-%d') if planned_date else None,
        'delivery_number': delivery_number,
        'is_wedding': is_wedding,
        'discount': discount,
        'action': action,
        'warnings': warnings,
        'recipient_social': (raw.get('recipient_social_raw') or '').strip(),
        'preferences': (raw.get('preferences_raw') or '').strip(),
    }


def preview_import_kvitkovapovnya(file_stream):
    """Parse and preview the Kvitkovapovnya 2026 CSV file."""
    raw_rows = parse_csv_rows_kvitkovapovnya(file_stream)
    preview_rows = []
    summary = {
        'total': 0,
        'new_clients': 0,
        'existing_clients': 0,
        'warnings': 0,
        'client_only': 0,
        'one_time': 0,
        'subscriptions': 0,
    }

    for raw in raw_rows:
        row = build_preview_row_kvitkovapovnya(raw)
        existing = find_existing_client(
            instagram=row['client_instagram'],
            telegram=row['client_telegram'],
            phone=row['client_phone_id'],
        )
        row['is_new_client'] = existing is None

        summary['total'] += 1
        if existing:
            summary['existing_clients'] += 1
        else:
            summary['new_clients'] += 1
        if row['warnings']:
            summary['warnings'] += len(row['warnings'])
        if row['action'] == 'client_only':
            summary['client_only'] += 1
        elif row['action'] == 'one_time':
            summary['one_time'] += 1
        else:
            summary['subscriptions'] += 1

        preview_rows.append(row)

    return preview_rows, summary


def execute_import_kvitkovapovnya(preview_rows):
    """Execute the import from preview rows."""
    from app.services.subscription_service import create_subscription_from_import
    from app.services.order_service import create_order_and_deliveries

    created_clients = 0
    existing_clients = 0
    created_orders = 0
    errors = []

    for row in preview_rows:
        try:
            with db.session.begin_nested():
                client = find_existing_client(
                    instagram=row.get('client_instagram'),
                    telegram=row.get('client_telegram'),
                    phone=row.get('client_phone_id'),
                )
                if not client:
                    client = Client(
                        instagram=row.get('client_instagram'),
                        telegram=row.get('client_telegram'),
                        phone=row['recipient_phone'] or row.get('client_phone_id') or '',
                    )
                    db.session.add(client)
                    db.session.flush()
                    created_clients += 1
                else:
                    existing_clients += 1

                if row.get('marketing_source'):
                    client.marketing_source = row['marketing_source']
                if row.get('discount'):
                    client.personal_discount = str(row['discount'])

                db.session.flush()

                action = row['action']
                if action != 'client_only':
                    planned_date = row.get('planned_date')
                    if not planned_date:
                        errors.append(f'Рядок {row["row_num"]} ({row["raw_client"]}): відсутня дата доставки')
                    else:
                        form = {
                            'recipient_name': row['recipient_name'] or '',
                            'recipient_phone': row['recipient_phone'] or '',
                            'additional_phones': row['recipient_phones_extra'] or [],
                            'city': row['city'],
                            'street': row['address_raw'],
                            'address_comment': row['address_comment'],
                            'building_number': '',
                            'floor': '',
                            'entrance': '',
                            'is_pickup': '',
                            'size': row['size'],
                            'custom_amount': '',
                            'first_delivery_date': planned_date,
                            'delivery_day': row['delivery_day'],
                            'time_from': '',
                            'time_to': '',
                            'comment': '',
                            'preferences': '',
                            'bouquet_type': '',
                            'composition_type': '',
                            'for_whom': row['for_whom'],
                            'delivery_method': row.get('delivery_method', 'courier'),
                            'delivery_type': row['delivery_type'],
                            'is_wedding': 'on' if row.get('is_wedding') else '',
                            'recipient_social': row.get('recipient_social') or '',
                            'preferences': row.get('preferences') or '',
                        }
                        if action == 'one_time':
                            create_order_and_deliveries(client, form)
                            created_orders += 1
                        elif action in ('subscription', 'subscription_followup'):
                            create_subscription_from_import(client, form, row['delivery_number'])
                            created_orders += 1

        except Exception as e:
            logger.error(f'KvP import error row {row["row_num"]}: {e}', exc_info=True)
            errors.append(f'Рядок {row["row_num"]} ({row["raw_client"]}): {e}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f'KvP commit error: {e}', exc_info=True)
        errors.append(f'Помилка збереження в БД: {e}')

    return {
        'created_clients': created_clients,
        'existing_clients': existing_clients,
        'created_orders': created_orders,
        'errors': errors,
    }
