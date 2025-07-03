from flask import Blueprint, render_template, request, redirect, url_for
from models import db, Price

prices_bp = Blueprint('prices', __name__)

@prices_bp.route('/prices', methods=['GET', 'POST'])
def prices():
    if request.method == 'POST':
        bouquet_size = request.form['bouquet_size']
        delivery_type = request.form['delivery_type']
        price = int(request.form['price'])
        price_obj = Price.query.filter_by(bouquet_size=bouquet_size, delivery_type=delivery_type).first()
        if price_obj:
            price_obj.price = price
        else:
            price_obj = Price(bouquet_size=bouquet_size, delivery_type=delivery_type, price=price)
            db.session.add(price_obj)
        db.session.commit()
        return redirect(url_for('prices.prices'))
    prices = Price.query.order_by(Price.bouquet_size, Price.delivery_type).all()
    return render_template('prices.html', prices=prices) 