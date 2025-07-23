from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from . import bp

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('orders.orders_list'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Ви успішно увійшли в систему!', 'success')
            
            # Перенаправлення на сторінку, яку користувач намагався відвідати
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('orders.orders_list')
            return redirect(next_page)
        
        flash('Невірний логін або пароль', 'danger')
    
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ви вийшли з системи', 'info')
    return redirect(url_for('auth.login')) 