import hmac

from flask import current_app, jsonify, request

from app.blueprints.integrations import integrations_bp
from app.services import wix_integration_service as wix_service


def _allowed_site_ids():
    raw = current_app.config.get('WIX_ALLOWED_SITE_IDS') or ''
    return {s.strip() for s in raw.split(',') if s.strip()}


@integrations_bp.route('/api/integrations/wix/order-placed', methods=['POST'])
def wix_order_webhook():
    allowed_ids = _allowed_site_ids()
    if not allowed_ids:
        return jsonify({'ok': False, 'error': 'integration not configured'}), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'error': 'invalid json body'}), 400

    parsed = wix_service.parse_wix_payload(payload)
    meta_site_id = parsed.get('meta_site_id')
    is_allowed = bool(meta_site_id) and any(
        hmac.compare_digest(meta_site_id, allowed) for allowed in allowed_ids
    )
    if not is_allowed:
        return jsonify({'ok': False, 'error': 'unknown site'}), 403

    try:
        lead = wix_service.create_or_update_lead(payload, parsed)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    return jsonify({'ok': True, 'lead_id': lead.id}), 200
