from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# In-memory список замовлень (оновлений для підтримки всіх полів)
orders = []

@app.route('/orders')
def orders_list():
    # Фільтрація
    phone = request.args.get('phone', '').strip()
    instagram = request.args.get('instagram', '').strip()
    city = request.args.get('city', '').strip()
    filtered = orders
    if phone:
        filtered = [o for o in filtered if phone in o.get('phone', '')]
    if instagram:
        filtered = [o for o in filtered if instagram.lower() in o.get('instagram', '').lower()]
    if city:
        filtered = [o for o in filtered if o.get('city', '') == city]
    # Пагінація
    page = int(request.args.get('page', 1))
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    orders_on_page = filtered[start:end]
    has_next = end < len(filtered)
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1
    # Унікальні міста для фільтра
    cities = sorted(set(o.get('city', '') for o in orders if o.get('city', '')))
    return render_template('orders_list.html', orders_on_page=orders_on_page, page=page, prev_page=prev_page, next_page=next_page, has_next=has_next, cities=cities)

@app.route('/orders/new', methods=['GET', 'POST'])
def order_create():
    if request.method == 'POST':
        order = {
            'id': len(orders) + 1,
            'instagram': request.form['instagram'],
            'city': request.form['city'],
            'street': request.form['street'],
            'building_number': request.form['building_number'],
            'floor': request.form['floor'],
            'entrance': request.form['entrance'],
            'phone': request.form['phone'],
            'type': request.form['type'],
            'size': request.form['size'],
            'time_window': request.form['time_window'],
            'comment': request.form['comment'],
        }
        orders.append(order)
        return redirect(url_for('orders_list'))
    return render_template('order_form.html')

@app.route('/')
def index():
    return redirect(url_for('orders_list'))

@app.route('/route-generator', methods=['GET', 'POST'])
def route_generator():
    if request.method == 'POST':
        # Тут буде логіка обробки CSV та генерації маршруту
        return render_template('route_generator.html', result='(Тут буде результат)')
    return render_template('route_generator.html')

if __name__ == '__main__':
    app.run(debug=True, port=5055) 