from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from app.models.delivery import Delivery
from sqlalchemy.orm import joinedload
from datetime import date, datetime, timedelta

florist_bp = Blueprint('florist', __name__)


@florist_bp.route('/florist')
@login_required
def florist_routes():
    today = date.today()
    date_str = request.args.get('date', '')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today
    except ValueError:
        selected_date = today

    routes = (
        DeliveryRoute.query
        .filter(
            DeliveryRoute.route_date == selected_date,
            DeliveryRoute.status.in_(['accepted', 'sent', 'draft'])
        )
        .order_by(DeliveryRoute.id)
        .all()
    )

    nova_poshta_deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order), joinedload(Delivery.client))
        .filter(
            Delivery.delivery_date == selected_date,
            Delivery.delivery_method == 'nova_poshta'
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    pickup_deliveries = (
        Delivery.query
        .options(joinedload(Delivery.order), joinedload(Delivery.client))
        .filter(
            Delivery.delivery_date == selected_date,
            Delivery.is_pickup == True
        )
        .order_by(Delivery.time_from.asc().nullslast(), Delivery.id.asc())
        .all()
    )

    return render_template(
        'florist/list.html',
        routes=routes,
        today=today,
        selected_date=selected_date,
        timedelta=timedelta,
        nova_poshta_deliveries=nova_poshta_deliveries,
        pickup_deliveries=pickup_deliveries,
    )
