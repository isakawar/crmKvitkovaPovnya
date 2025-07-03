from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from app.services.price_service import get_all_prices, create_or_update_price, update_price_by_id

prices_bp = Blueprint('prices', __name__)

@prices_bp.route('/prices', methods=['GET', 'POST'])
def prices():
    if request.method == 'POST':
        bouquet_size = request.form['bouquet_size']
        delivery_type = request.form['delivery_type']
        price = int(request.form['price'])
        create_or_update_price(bouquet_size, delivery_type, price)
        return redirect(url_for('prices.prices'))
    prices = get_all_prices()
    return render_template('prices.html', prices=prices)

@prices_bp.route('/prices/<int:price_id>', methods=['PUT', 'PATCH'])
def update_price(price_id):
    data = request.json
    bouquet_size = data.get('bouquet_size')
    delivery_type = data.get('delivery_type')
    price = data.get('price')
    price_obj, error = update_price_by_id(price_id, bouquet_size, delivery_type, price)
    if price_obj:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': error}), 400 