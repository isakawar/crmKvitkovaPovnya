from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models.delivery_route import DeliveryRoute, RouteDelivery
from datetime import date

florist_bp = Blueprint('florist', __name__)


@florist_bp.route('/florist')
@login_required
def florist_routes():
    today = date.today()
    routes = (
        DeliveryRoute.query
        .filter(
            DeliveryRoute.route_date == today,
            DeliveryRoute.status.in_(['accepted', 'sent', 'draft'])
        )
        .order_by(DeliveryRoute.id)
        .all()
    )
    return render_template('florist_routes.html', routes=routes, today=today)
