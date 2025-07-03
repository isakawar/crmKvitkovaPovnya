from flask import Blueprint, render_template
from models import db, Order, Client

deliveries_bp = Blueprint('deliveries', __name__)

@deliveries_bp.route('/deliveries', methods=['GET'])
def deliveries_list():
    deliveries = Order.query.filter_by(type='Доставка').order_by(Order.id.desc()).all()
    return render_template('deliveries_list.html', deliveries=deliveries) 