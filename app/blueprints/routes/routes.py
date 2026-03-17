from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.models.courier import Courier
from datetime import datetime
import json
import urllib.parse
import requests as http_requests

routes_bp = Blueprint('routes', __name__)


def _telegram_send(bot_token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        resp = http_requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if data.get('ok'):
            return data['result']['message_id']
    except Exception:
        pass
    return None


def _telegram_edit(bot_token, chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        http_requests.post(url, json=payload, timeout=30)
    except Exception:
        pass


@routes_bp.route('/routes', methods=['GET'])
@login_required
def saved_routes():
    date_filter = request.args.get('date', '')
    query = DeliveryRoute.query.order_by(
        DeliveryRoute.route_date.desc(), DeliveryRoute.created_at.desc()
    )
    if date_filter:
        try:
            d = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(route_date=d)
        except ValueError:
            pass
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.client import Client
    from datetime import date as date_type
    routes = query.options(
        joinedload(DeliveryRoute.stops)
            .joinedload(RouteDelivery.delivery)
            .joinedload(Delivery.order),
        joinedload(DeliveryRoute.stops)
            .joinedload(RouteDelivery.delivery)
            .joinedload(Delivery.client),
    ).all()
    couriers = Courier.query.filter_by(active=True).order_by(Courier.name).all()

    # Nova Poshta deliveries for selected date
    np_date = None
    if date_filter:
        try:
            np_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            pass
    if np_date is None:
        np_date = date_type.today()
    nova_poshta_deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order), joinedload(Delivery.client))
        .filter(
            Delivery.delivery_date == np_date,
            Delivery.delivery_method == 'nova_poshta'
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    pickup_deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order), joinedload(Delivery.client))
        .filter(
            Delivery.delivery_date == np_date,
            Delivery.is_pickup == True
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    return render_template(
        'routes/saved.html',
        routes=routes,
        couriers=couriers,
        date_filter=date_filter,
        nova_poshta_deliveries=nova_poshta_deliveries,
        pickup_deliveries=pickup_deliveries,
        np_date=np_date,
    )


@routes_bp.route('/routes/<int:route_id>/assign', methods=['POST'])
@login_required
def assign_route(route_id):
    route = DeliveryRoute.query.get_or_404(route_id)
    courier_id = request.form.get('courier_id', type=int)
    delivery_price = request.form.get('delivery_price', type=int)

    # Notify old courier if route was sent and courier is being changed
    old_courier_id = route.courier_id
    new_courier_id = courier_id or None
    if old_courier_id and old_courier_id != new_courier_id and route.telegram_message_id:
        old_courier = Courier.query.get(old_courier_id)
        if old_courier and old_courier.telegram_chat_id:
            bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
            cancel_text = (
                f"⚠️ <b>Маршрут на {route.route_date.strftime('%d.%m.%Y')} більше не актуальний.</b>\n\n"
                f"Призначення було змінено. Ця пропозиція скасована."
            )
            _telegram_edit(bot_token, old_courier.telegram_chat_id, route.telegram_message_id, cancel_text)
        route.telegram_message_id = None
        route.status = 'draft'

    route.courier_id = new_courier_id
    if delivery_price is not None:
        route.delivery_price = delivery_price
    db.session.commit()
    return redirect(url_for('routes.saved_routes'))



@routes_bp.route('/routes/<int:route_id>/assign-and-send', methods=['POST'])
@login_required
def assign_and_send_route(route_id):
    route = DeliveryRoute.query.get_or_404(route_id)
    courier_id = request.form.get('courier_id', type=int)
    delivery_price = request.form.get('delivery_price', type=int)

    if not courier_id:
        flash('Оберіть кур\'єра', 'warning')
        return redirect(url_for('routes.saved_routes'))

    courier = Courier.query.get(courier_id)
    if not courier or not courier.telegram_chat_id:
        flash('Кур\'єр не зареєстрований в Telegram', 'danger')
        return redirect(url_for('routes.saved_routes'))

    # Notify old courier if route was already sent and courier is being changed
    old_courier_id = route.courier_id
    if old_courier_id and old_courier_id != courier_id and route.telegram_message_id:
        old_courier = Courier.query.get(old_courier_id)
        if old_courier and old_courier.telegram_chat_id:
            bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
            cancel_text = (
                f"⚠️ <b>Маршрут на {route.route_date.strftime('%d.%m.%Y')} більше не актуальний.</b>\n\n"
                f"Призначення було змінено. Ця пропозиція скасована."
            )
            _telegram_edit(bot_token, old_courier.telegram_chat_id, route.telegram_message_id, cancel_text)
        route.telegram_message_id = None

    route.courier_id = courier_id
    if delivery_price is not None:
        route.delivery_price = delivery_price
    db.session.commit()

    stops = RouteDelivery.query.filter_by(route_id=route_id).order_by(RouteDelivery.stop_order).all()

    text = f"🌸 <b>Пропозиція маршруту на {route.route_date.strftime('%d.%m.%Y')}</b>\n\n"
    text += f"📦 Доставок: <b>{route.deliveries_count}</b>\n"
    if route.delivery_price:
        text += f"💰 Оплата: <b>{route.delivery_price}₴</b>\n"
    text += "\n<b>Маршрут:</b>\n"
    for stop in stops:
        d = stop.delivery
        order = d.order if d else None
        city = (order.city if order else '') or ''
        street = (d.street or (order.street if order else '')) or '—'
        build = (d.building_number or (order.building_number if order else '')) or ''
        arrival = stop.planned_arrival.strftime('%H:%M') if stop.planned_arrival else '—'
        addr_parts = [p for p in [city, street, build] if p]
        text += f"\n{stop.stop_order}. {', '.join(addr_parts)} — {arrival}"

    depot_address = current_app.config.get('DEPOT_ADDRESS', '').strip()
    gmaps_parts = []
    if depot_address:
        gmaps_parts.append(urllib.parse.quote(depot_address))
    for stop in stops:
        d = stop.delivery
        order = d.order if d else None
        parts = [p for p in [
            (order.city if order else '') or '',
            (d.street or (order.street if order else '')) or '',
            (d.building_number or (order.building_number if order else '')) or '',
        ] if p]
        if parts:
            gmaps_parts.append(urllib.parse.quote(', '.join(parts)))
    gmaps_url = 'https://www.google.com/maps/dir/' + '/'.join(gmaps_parts) if gmaps_parts else None

    inline_keyboard = []
    if gmaps_url:
        inline_keyboard.append([{'text': '🗺 Переглянути маршрут на Google Maps', 'url': gmaps_url}])
    inline_keyboard.append([
        {'text': '✅ Прийняти', 'callback_data': f'route_accept_{route_id}'},
        {'text': '❌ Відхилити', 'callback_data': f'route_reject_{route_id}'},
    ])

    bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
    msg_id = _telegram_send(bot_token, courier.telegram_chat_id, text, {'inline_keyboard': inline_keyboard})

    if not msg_id:
        flash('Кур\'єра призначено, але надіслати в Telegram не вдалось. Перевірте токен та chat_id.', 'warning')
        return redirect(url_for('routes.saved_routes'))

    route.status = 'sent'
    route.telegram_message_id = msg_id
    route.sent_at = datetime.utcnow()
    db.session.commit()

    flash(f'Маршрут призначено та надіслано кур\'єру {courier.name}', 'success')
    return redirect(url_for('routes.saved_routes'))


@routes_bp.route('/routes/<int:route_id>/delete', methods=['POST'])
@login_required
def delete_route(route_id):
    route = DeliveryRoute.query.get_or_404(route_id)
    db.session.delete(route)
    db.session.commit()
    flash('Маршрут видалено', 'success')
    return redirect(url_for('routes.saved_routes'))
