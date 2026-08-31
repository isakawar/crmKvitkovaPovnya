import logging
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.services.csv_import_service import normalize_phone
from app.models import Client
from app.models.wix_product_mapping import WixProductMapping
from app.models.wix_lead import WixLead
from app.models.order import Order
from app.models.subscription import Subscription
from app.telegram_bot.manager_notification_service import notify_lead_processed


def parse_wix_payload(payload: dict) -> dict:
    """Extract the fields the CRM needs from a Wix 'order placed' webhook body.

    Accepts either the raw Wix Automations body ({"data": {...}}) or the
    unwrapped order object directly, for easier testing.
    """
    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def _as_list(value):
        return value if isinstance(value, list) else []

    if isinstance(payload, dict) and 'data' in payload:
        order_data = _as_dict(payload.get('data'))
    else:
        order_data = _as_dict(payload)

    contact = _as_dict(order_data.get('contact'))
    name = _as_dict(contact.get('name'))
    contact_name = ' '.join(p for p in [name.get('first'), name.get('last')] if p).strip() or None

    contact_phone = None
    phones = _as_list(contact.get('phones'))
    primary_phone = next((p for p in phones if isinstance(p, dict) and p.get('primary')), None)
    phone_source = primary_phone or next((p for p in phones if isinstance(p, dict)), None)
    if phone_source and phone_source.get('e164Phone'):
        contact_phone = normalize_phone(phone_source['e164Phone'])

    contact_email = contact.get('email') or order_data.get('buyerEmail')

    shipping_dest = _as_dict(
        _as_dict(_as_dict(order_data.get('shippingInfo')).get('logistics')).get('shippingDestination')
    )
    address = _as_dict(shipping_dest.get('address')) or _as_dict(contact.get('address'))
    shipping_contact = _as_dict(shipping_dest.get('contactDetails'))

    if not contact_phone and shipping_contact.get('phone'):
        contact_phone = normalize_phone(shipping_contact['phone'])

    if not contact_name:
        contact_name = ' '.join(
            p for p in [shipping_contact.get('firstName'), shipping_contact.get('lastName')] if p
        ).strip() or None

    line_items = _as_list(order_data.get('lineItems'))
    first_item = _as_dict(line_items[0]) if line_items else {}

    # catalogItemId may be flat (automation payload) or nested under
    # catalogReference (Orders API); accept either.
    catalog_item_id = (
        first_item.get('catalogItemId')
        or _as_dict(first_item.get('catalogReference')).get('catalogItemId')
    )
    item_name = first_item.get('itemName') or _as_dict(first_item.get('productName')).get('original')

    price_summary = _as_dict(order_data.get('priceSummary'))
    total = _as_dict(price_summary.get('total'))
    total_price = _as_dict(first_item.get('totalPrice'))

    # Checkout custom fields live in extendedFields._user_fields (Orders API only).
    user_fields = _as_dict(
        _as_dict(_as_dict(order_data.get('extendedFields')).get('namespaces')).get('_user_fields')
    )
    custom_fields = {k: v for k, v in user_fields.items() if v not in (None, '')}

    return {
        'wix_order_id': order_data.get('id'),
        'wix_order_number': order_data.get('orderNumber'),
        'meta_site_id': _as_dict(order_data.get('context')).get('metaSiteId'),
        'contact_name': contact_name,
        'contact_phone': contact_phone,
        'contact_email': contact_email,
        'city': address.get('city'),
        'street': address.get('addressLine'),
        'postal_code': address.get('postalCode'),
        'address_comment': None,
        'item_name': item_name,
        'catalog_item_id': catalog_item_id,
        'quantity': first_item.get('quantity'),
        'amount': total.get('value') or total_price.get('value'),
        'currency': total.get('currency') or order_data.get('currency'),
        'payment_status': order_data.get('paymentStatus'),
        'line_items_count': len(line_items),
        'buyer_note': order_data.get('buyerNote') or _as_dict(order_data.get('buyerInfo')).get('note'),
        'custom_fields': custom_fields or None,
    }


def find_matching_client(parsed: dict):
    """Match a parsed Wix order to an existing client by phone (first) or email (fallback).

    Args:
        parsed: dict with 'contact_phone' and 'contact_email' keys

    Returns:
        Client object if found, None otherwise
    """
    phone = parsed.get('contact_phone')
    if phone:
        client = Client.query.filter_by(phone=phone).first()
        if client:
            return client
    email = parsed.get('contact_email')
    if email:
        client = Client.query.filter_by(email=email).first()
        if client:
            return client
    return None


def match_client_for_lead(lead):
    """Live client match for a lead by its stored phone/email.

    Used at display/processing time so a client created *after* the webhook
    arrived is still picked up (the stored `matched_client_id` is only set once).
    """
    return find_matching_client({
        'contact_phone': lead.contact_phone,
        'contact_email': lead.contact_email,
    })


def find_product_mapping(catalog_item_id):
    """Find an active product mapping by Wix catalog_item_id.

    Args:
        catalog_item_id: str or None - the Wix catalog item ID

    Returns:
        WixProductMapping object if found and active, None otherwise
    """
    if not catalog_item_id:
        return None
    return WixProductMapping.query.filter_by(
        catalog_item_id=catalog_item_id, is_active=True
    ).first()


def create_or_update_lead(payload: dict, parsed: dict) -> WixLead:
    wix_order_id = parsed.get('wix_order_id')
    if not wix_order_id:
        raise ValueError('Wix payload missing order id (data.id)')

    existing = WixLead.query.filter_by(wix_order_id=wix_order_id).first()
    if existing and existing.status != 'new':
        return existing

    client = find_matching_client(parsed)
    mapping = find_product_mapping(parsed.get('catalog_item_id'))

    lead = existing or WixLead(wix_order_id=wix_order_id)
    lead.wix_order_number = parsed.get('wix_order_number')
    lead.raw_payload = payload
    lead.status = 'new'
    lead.received_at = lead.received_at or datetime.utcnow()
    lead.contact_name = parsed.get('contact_name')
    lead.contact_phone = parsed.get('contact_phone')
    lead.contact_email = parsed.get('contact_email')
    lead.city = parsed.get('city')
    lead.street = parsed.get('street')
    lead.postal_code = parsed.get('postal_code')
    lead.address_comment = parsed.get('address_comment')
    lead.item_name = parsed.get('item_name')
    lead.catalog_item_id = parsed.get('catalog_item_id')
    lead.quantity = parsed.get('quantity')
    lead.amount = parsed.get('amount')
    lead.currency = parsed.get('currency')
    lead.payment_status = parsed.get('payment_status')
    lead.line_items_count = parsed.get('line_items_count')
    lead.buyer_note = parsed.get('buyer_note')
    lead.custom_fields = parsed.get('custom_fields')
    lead.matched_client_id = client.id if client else None
    lead.mapping_matched = mapping is not None

    db.session.add(lead)
    db.session.commit()
    return lead


# --- Wix Orders API enrichment ------------------------------------------------
#
# The `wix_e_commerce-order_placed` automation payload omits checkout custom
# fields (`extendedFields._user_fields`) and the buyer note. We fetch the full
# order from the Orders API and splice those two pieces into the payload before
# parsing, so `parse_wix_payload` keeps working on the familiar shape.

WIX_ORDERS_API_URL = 'https://www.wixapis.com/ecom/v1/orders/'


def fetch_full_wix_order(order_id: str) -> dict | None:
    """Return the full Wix order dict, or None if not configured / unavailable."""
    api_key = current_app.config.get('WIX_API_KEY')
    site_id = current_app.config.get('WIX_SITE_ID')
    if not api_key or not site_id or not order_id:
        return None

    import requests

    try:
        resp = requests.get(
            WIX_ORDERS_API_URL + order_id,
            headers={'Authorization': api_key, 'wix-site-id': site_id},
            timeout=15,
        )
        if resp.status_code != 200:
            logging.warning('Wix Orders API %s for order %s: %s',
                            resp.status_code, order_id, resp.text[:300])
            return None
        return resp.json().get('order')
    except Exception:
        logging.warning('Wix Orders API request failed for order %s', order_id, exc_info=True)
        return None


def enrich_payload_with_order_api(payload: dict) -> dict:
    """Splice buyerNote + extendedFields from the Orders API into the webhook payload.

    Mutates and returns `payload`. No-op if the API is not configured or the
    fetch fails — the lead is still created from what the webhook delivered.
    """
    data = payload.get('data')
    if not isinstance(data, dict):
        return payload
    if data.get('extendedFields') and data.get('buyerNote') is not None:
        return payload  # already complete

    order = fetch_full_wix_order(data.get('id'))
    if not order:
        return payload

    if order.get('extendedFields') is not None:
        data['extendedFields'] = order['extendedFields']
    if order.get('buyerNote') is not None:
        data['buyerNote'] = order['buyerNote']
    return payload


# Ukrainian cadence label (from the checkout dropdown) -> CRM delivery_type
_CADENCE_MAP = {
    'weekly': 'Weekly', 'monthly': 'Monthly', 'bi-weekly': 'Bi-weekly',
    'щотижня': 'Weekly', 'щотижнева': 'Weekly', 'щотижнево': 'Weekly',
    'раз на тиждень': 'Weekly',
    'щомісяця': 'Monthly', 'щомісячна': 'Monthly', 'раз на місяць': 'Monthly',
    'раз на 2 тижні': 'Bi-weekly', 'раз на два тижні': 'Bi-weekly',
    'двотижнева': 'Bi-weekly', 'кожні 2 тижні': 'Bi-weekly',
}


def _match_field(custom_fields: dict, *needles):
    """Return the value of the first custom field whose slug contains any needle."""
    for slug, value in (custom_fields or {}).items():
        low = slug.lower()
        if any(n in low for n in needles):
            return value
    return None


def resolve_requested_delivery_type(custom_fields: dict):
    raw = _match_field(custom_fields, 'periodichn', 'period', 'cadence', 'frequency')
    if not raw:
        return None
    return _CADENCE_MAP.get(str(raw).strip().lower())


def resolve_requested_first_delivery_date(custom_fields: dict):
    raw = _match_field(custom_fields, 'data_pershoyi', 'pershoi', 'first_delivery', 'delivery_date')
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def resolve_customer_wishes(lead) -> str | None:
    parts = []
    if lead.buyer_note:
        parts.append(lead.buyer_note.strip())
    wish = _match_field(lead.custom_fields, 'pobazhann', 'wish', 'comment', 'note')
    if wish and str(wish).strip():
        parts.append(str(wish).strip())
    return ' | '.join(parts) or None


# Wix auto-generates checkout-field slugs by transliterating the label. Map the
# known ones back to a readable Ukrainian label; unknown slugs fall back to a
# de-slugified form ("data_something" -> "Data something").
_CUSTOM_FIELD_LABELS = [
    (('periodichn', 'period', 'cadence', 'frequency'), 'Періодичність доставки'),
    (('data_pershoyi', 'pershoi', 'first_delivery', 'delivery_date'), 'Дата першої доставки'),
    (('pobazhann', 'wish'), 'Побажання'),
    (('nomer_telefonu', 'phone', 'telefon'), 'Номер телефону замовника'),
]


def humanize_custom_field_key(slug: str) -> str:
    low = (slug or '').lower()
    for needles, label in _CUSTOM_FIELD_LABELS:
        if any(n in low for n in needles):
            return label
    return (slug or '').replace('_', ' ').strip().capitalize()


def humanize_custom_fields(custom_fields: dict) -> list[dict]:
    """[{label, value}] for display in the lead reference card."""
    return [
        {'label': humanize_custom_field_key(k), 'value': v}
        for k, v in (custom_fields or {}).items()
        if v not in (None, '')
    ]


def mark_lead_processed(lead: WixLead, entity, user) -> None:
    lead.status = 'processed'
    lead.processed_at = datetime.utcnow()
    lead.processed_by_user_id = getattr(user, 'id', None)

    if isinstance(entity, Subscription):
        lead.processed_subscription_id = entity.id
        lead.processed_order_id = entity.orders[0].id if entity.orders else None
    elif isinstance(entity, Order):
        lead.processed_order_id = entity.id

    db.session.commit()

    try:
        notify_lead_processed(lead)
    except Exception:
        logging.warning(
            f'Wix lead {lead.id}: failed to send processed Telegram notification', exc_info=True
        )


def fetch_wix_products(api_key: str, site_id: str) -> list[dict]:
    """Fetch the full Wix Stores catalog via the REST API.

    Returns a list of dicts: {id, name, sku, price, currency, product_type,
    visible, mapped} — one per product, sorted by name. ``mapped`` reflects
    whether an active WixProductMapping already exists for that catalog id.

    Raises RuntimeError on a non-2xx response.
    """
    import requests

    known_ids = {
        m.catalog_item_id
        for m in WixProductMapping.query.filter_by(is_active=True).all()
    }

    url = 'https://www.wixapis.com/stores-reader/v1/products/query'
    headers = {
        'Authorization': api_key,
        'wix-site-id': site_id,
        'Content-Type': 'application/json',
    }

    products: list[dict] = []
    offset = 0
    limit = 100
    while True:
        body = {'query': {'paging': {'limit': limit, 'offset': offset}}}
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f'Wix API {resp.status_code}: {resp.text[:500]}')
        data = resp.json()
        batch = data.get('products', []) or []
        for p in batch:
            price_data = p.get('priceData') or p.get('price') or {}
            products.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'sku': p.get('sku') or '',
                'price': price_data.get('price') or price_data.get('discountedPrice'),
                'currency': price_data.get('currency') or '',
                'product_type': p.get('productType') or '',
                'visible': p.get('visible', True),
                'mapped': p.get('id') in known_ids,
            })
        total = (data.get('metadata') or {}).get('count') or data.get('totalResults')
        offset += limit
        if not batch or (total is not None and offset >= total) or len(batch) < limit:
            break

    products.sort(key=lambda x: (x['name'] or '').lower())
    return products
