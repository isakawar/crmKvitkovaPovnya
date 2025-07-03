from flask import Blueprint, render_template
from models import db, Delivery, Order, Client

deliveries_bp = Blueprint('deliveries', __name__)

@deliveries_bp.route('/deliveries', methods=['GET'])
def deliveries_list():
    deliveries = Delivery.query.order_by(Delivery.id.desc()).all()
    return render_template('deliveries_list.html', deliveries=deliveries) 