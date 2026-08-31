import logging

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.integrations import integrations_bp
from app.extensions import db
from app.models.wix_lead import WixLead
from app.models.wix_product_mapping import WixProductMapping
from app.services import wix_integration_service as wix_service
from app.telegram_bot.manager_notification_service import send_new_lead_notification


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
        logging.warning(
            'Wix webhook: invalid JSON body. content_type=%r raw=%r',
            request.content_type, request.get_data(as_text=True)[:2000],
        )
        return jsonify({'ok': False, 'error': 'invalid json body'}), 400

    # metaSiteId is not secret (it's visible in every public Wix site's page
    # source), so a plain membership check is fine here - no need for
    # constant-time comparison, and it avoids hmac.compare_digest's TypeError
    # on non-str input.
    data = payload.get('data')
    data = data if isinstance(data, dict) else {}
    context = data.get('context')
    context = context if isinstance(context, dict) else {}
    meta_site_id = context.get('metaSiteId')
    if not isinstance(meta_site_id, str) or meta_site_id not in allowed_ids:
        logging.warning(
            'Wix webhook rejected: metaSiteId=%r allowed=%r top_level_keys=%r',
            meta_site_id, sorted(allowed_ids), sorted(payload.keys()),
        )
        return jsonify({'ok': False, 'error': 'unknown site'}), 403

    try:
        payload = wix_service.enrich_payload_with_order_api(payload)
        parsed = wix_service.parse_wix_payload(payload)
        wix_order_id = parsed.get('wix_order_id')
        existing_before = (
            WixLead.query.filter_by(wix_order_id=wix_order_id).first() if wix_order_id else None
        )
        lead = wix_service.create_or_update_lead(payload, parsed)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        logging.warning('Wix webhook: failed to parse/process payload', exc_info=True)
        return jsonify({'ok': False, 'error': 'malformed payload'}), 400

    logging.info(f'Wix webhook: lead {lead.id} (wix_order_id={lead.wix_order_id}) accepted')

    if existing_before is None:
        try:
            send_new_lead_notification(lead)
        except Exception:
            logging.warning(
                f'Wix webhook: failed to send new-lead Telegram notification for lead {lead.id}',
                exc_info=True,
            )

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

    # Live client match (a client created after the webhook is still picked up)
    lead_clients = {
        lead.id: wix_service.match_client_for_lead(lead) for lead in leads
    }

    # Settings needed by the shared order composer + client modals
    from app.models.settings import Settings
    delivery_types = Settings.query.filter_by(type='delivery_type').order_by(Settings.value).all()
    sizes = Settings.query.filter_by(type='size').order_by(
        Settings.sort_order.nullslast(), Settings.value).all()
    for_whom = Settings.query.filter_by(type='for_whom').order_by(Settings.value).all()
    marketing_sources = Settings.query.filter_by(type='marketing_source').order_by(Settings.value).all()

    return render_template(
        'integrations/leads_list.html', leads=leads, status_filter=status_filter,
        lead_clients=lead_clients,
        delivery_types=delivery_types, sizes=sizes, for_whom=for_whom,
        marketing_sources=marketing_sources,
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

    if WixProductMapping.query.filter_by(catalog_item_id=catalog_item_id).first():
        flash(f'Мапінг для catalog_item_id "{catalog_item_id}" вже існує', 'danger')
        return redirect(url_for('integrations.wix_product_mappings_list'))

    mapping = WixProductMapping(
        catalog_item_id=catalog_item_id,
        wix_item_name=(request.form.get('wix_item_name') or '').strip() or None,
        order_scenario=order_scenario,
        delivery_type=(request.form.get('delivery_type') or '').strip() or None,
        size=size,
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
