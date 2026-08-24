from app.services.csv_import_service import normalize_phone
from app.models import Client
from app.models.wix_product_mapping import WixProductMapping


def parse_wix_payload(payload: dict) -> dict:
    """Extract the fields the CRM needs from a Wix 'order placed' webhook body.

    Accepts either the raw Wix Automations body ({"data": {...}}) or the
    unwrapped order object directly, for easier testing.
    """
    if isinstance(payload, dict) and 'data' in payload:
        order_data = payload.get('data') or {}
    else:
        order_data = payload or {}

    contact = order_data.get('contact') or {}
    name = contact.get('name') or {}
    contact_name = ' '.join(p for p in [name.get('first'), name.get('last')] if p).strip() or None

    contact_phone = None
    phones = contact.get('phones') or []
    primary_phone = next((p for p in phones if p.get('primary')), None)
    phone_source = primary_phone or (phones[0] if phones else None)
    if phone_source and phone_source.get('e164Phone'):
        contact_phone = normalize_phone(phone_source['e164Phone'])

    contact_email = contact.get('email') or order_data.get('buyerEmail')

    shipping_dest = (
        (order_data.get('shippingInfo') or {}).get('logistics') or {}
    ).get('shippingDestination') or {}
    address = shipping_dest.get('address') or contact.get('address') or {}
    shipping_contact = shipping_dest.get('contactDetails') or {}

    if not contact_phone and shipping_contact.get('phone'):
        contact_phone = normalize_phone(shipping_contact['phone'])

    if not contact_name:
        contact_name = ' '.join(
            p for p in [shipping_contact.get('firstName'), shipping_contact.get('lastName')] if p
        ).strip() or None

    line_items = order_data.get('lineItems') or []
    first_item = line_items[0] if line_items else {}

    price_summary = order_data.get('priceSummary') or {}
    total = price_summary.get('total') or {}
    total_price = first_item.get('totalPrice') or {}

    return {
        'wix_order_id': order_data.get('id'),
        'wix_order_number': order_data.get('orderNumber'),
        'meta_site_id': (order_data.get('context') or {}).get('metaSiteId'),
        'contact_name': contact_name,
        'contact_phone': contact_phone,
        'contact_email': contact_email,
        'city': address.get('city'),
        'street': address.get('addressLine'),
        'postal_code': address.get('postalCode'),
        'address_comment': None,
        'item_name': first_item.get('itemName'),
        'catalog_item_id': first_item.get('catalogItemId'),
        'quantity': first_item.get('quantity'),
        'amount': total.get('value') or total_price.get('value'),
        'currency': total.get('currency') or order_data.get('currency'),
        'payment_status': order_data.get('paymentStatus'),
        'line_items_count': len(line_items),
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
