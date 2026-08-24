import hmac

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.integrations import integrations_bp
from app.extensions import db
from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping
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


def _is_admin_or_manager():
    return getattr(current_user, 'user_type', None) in ('admin', 'manager')


@integrations_bp.route('/integrations/wix-leads', methods=['GET'])
@login_required
def wix_leads_list():
    if not _is_admin_or_manager():
        abort(403)
    status_filter = request.args.get('status', 'new')
    query = WixLead.query
    if status_filter in ('new', 'processed', 'ignored'):
        query = query.filter_by(status=status_filter)
    leads = query.order_by(WixLead.received_at.desc()).all()
    return render_template(
        'integrations/leads_list.html', leads=leads, status_filter=status_filter
    )


@integrations_bp.route('/integrations/wix-leads/<int:lead_id>/ignore', methods=['POST'])
@login_required
def wix_lead_ignore(lead_id):
    if not _is_admin_or_manager():
        abort(403)
    lead = WixLead.query.get_or_404(lead_id)
    lead.status = 'ignored'
    db.session.commit()
    flash('Заявку проігноровано', 'success')
    return redirect(url_for('integrations.wix_leads_list'))


@integrations_bp.route('/integrations/wix-product-mappings', methods=['GET'])
@login_required
def wix_product_mappings_list():
    if not _is_admin_or_manager():
        abort(403)
    mappings = WixProductMapping.query.order_by(WixProductMapping.id.desc()).all()
    return render_template('integrations/product_mappings.html', mappings=mappings)


@integrations_bp.route('/integrations/wix-product-mappings/new', methods=['POST'])
@login_required
def wix_product_mapping_create():
    if not _is_admin_or_manager():
        abort(403)
    catalog_item_id = (request.form.get('catalog_item_id') or '').strip()
    order_scenario = request.form.get('order_scenario') or ''
    size = request.form.get('size') or ''
    if not catalog_item_id or order_scenario not in ('order', 'subscription') or not size:
        flash('Заповніть catalog_item_id, сценарій і розмір', 'danger')
        return redirect(url_for('integrations.wix_product_mappings_list'))

    mapping = WixProductMapping(
        catalog_item_id=catalog_item_id,
        wix_item_name=(request.form.get('wix_item_name') or '').strip() or None,
        order_scenario=order_scenario,
        delivery_type=(request.form.get('delivery_type') or '').strip() or None,
        size=size,
        for_whom=(request.form.get('for_whom') or '').strip() or None,
    )
    db.session.add(mapping)
    db.session.commit()
    flash('Мапінг додано', 'success')
    return redirect(url_for('integrations.wix_product_mappings_list'))


@integrations_bp.route('/integrations/wix-product-mappings/<int:mapping_id>/edit', methods=['POST'])
@login_required
def wix_product_mapping_edit(mapping_id):
    if not _is_admin_or_manager():
        abort(403)
    mapping = WixProductMapping.query.get_or_404(mapping_id)
    mapping.wix_item_name = (request.form.get('wix_item_name') or '').strip() or None
    mapping.order_scenario = request.form.get('order_scenario') or mapping.order_scenario
    mapping.delivery_type = (request.form.get('delivery_type') or '').strip() or None
    mapping.size = request.form.get('size') or mapping.size
    mapping.for_whom = (request.form.get('for_whom') or '').strip() or None
    mapping.is_active = request.form.get('is_active') == 'on'
    db.session.commit()
    flash('Мапінг оновлено', 'success')
    return redirect(url_for('integrations.wix_product_mappings_list'))


@integrations_bp.route('/integrations/wix-product-mappings/<int:mapping_id>/delete', methods=['POST'])
@login_required
def wix_product_mapping_delete(mapping_id):
    if not _is_admin_or_manager():
        abort(403)
    mapping = WixProductMapping.query.get_or_404(mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    flash('Мапінг видалено', 'success')
    return redirect(url_for('integrations.wix_product_mappings_list'))
