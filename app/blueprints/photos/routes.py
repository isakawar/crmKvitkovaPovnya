import mimetypes
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, abort, jsonify
from flask_login import current_user, login_required
from app.services import photo_service
from app.models import Order

photos_bp = Blueprint('photos', __name__, url_prefix='/photos')


def _can_delete():
    return getattr(current_user, 'user_type', None) in ('admin', 'manager')


@photos_bp.route('/')
@login_required
def list_photos():
    order_id = request.args.get('order_id', type=int)
    page = request.args.get('page', 1, type=int)
    pagination = photo_service.get_all_photos(page=page, per_page=25, order_id=order_id)
    return render_template(
        'photos/list.html',
        pagination=pagination,
        photos=pagination.items,
        order_id_filter=order_id,
        can_delete=_can_delete(),
    )


@photos_bp.route('/upload', methods=['POST'])
@login_required
def upload_photo():
    order_id = request.form.get('order_id', type=int)
    comment = request.form.get('comment', '').strip()
    file = request.files.get('photo')

    if not order_id:
        flash('Вкажіть ID замовлення', 'danger')
        return redirect(url_for('photos.list_photos'))

    order = Order.query.get(order_id)
    if not order:
        flash(f'Замовлення #{order_id} не знайдено', 'danger')
        return redirect(url_for('photos.list_photos'))

    _, error = photo_service.save_photo(file, order_id, current_user.id, comment)
    if error:
        flash(error, 'danger')
    else:
        flash('Фото завантажено', 'success')

    return redirect(url_for('photos.list_photos', order_id=order_id))


@photos_bp.route('/file/<filename>')
@login_required
def serve_photo(filename):
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'uploads', 'order_photos')
    mimetype, _ = mimetypes.guess_type(filename)
    if not mimetype or not mimetype.startswith('image/'):
        mimetype = 'image/webp'
    return send_from_directory(upload_folder, filename, mimetype=mimetype)


@photos_bp.route('/order/<int:order_id>/json')
@login_required
def order_photos_json(order_id):
    photos = photo_service.get_photos_for_order(order_id)
    return jsonify([{
        'id': p.id,
        'filename': p.filename,
        'original_name': p.original_name,
        'url': url_for('photos.serve_photo', filename=p.filename),
        'can_delete': _can_delete(),
    } for p in photos])


@photos_bp.route('/upload/ajax', methods=['POST'])
@login_required
def upload_photo_ajax():
    order_id = request.form.get('order_id', type=int)
    comment = request.form.get('comment', '').strip()
    file = request.files.get('photo')

    if not order_id:
        return jsonify({'success': False, 'error': 'Вкажіть ID замовлення'}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({'success': False, 'error': f'Замовлення #{order_id} не знайдено'}), 404

    photo, error = photo_service.save_photo(file, order_id, current_user.id, comment)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    return jsonify({
        'success': True,
        'photo': {
            'id': photo.id,
            'filename': photo.filename,
            'original_name': photo.original_name,
            'url': url_for('photos.serve_photo', filename=photo.filename),
            'can_delete': _can_delete(),
        }
    })


@photos_bp.route('/<int:photo_id>/delete/ajax', methods=['POST'])
@login_required
def delete_photo_ajax(photo_id):
    if not _can_delete():
        return jsonify({'success': False, 'error': 'Недостатньо прав'}), 403
    ok, error = photo_service.delete_photo(photo_id)
    if not ok:
        return jsonify({'success': False, 'error': error}), 404
    return jsonify({'success': True})


@photos_bp.route('/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_photos():
    if not _can_delete():
        return jsonify({'success': False, 'error': 'Недостатньо прав'}), 403
    ids = request.json.get('ids', []) if request.is_json else request.form.getlist('ids', type=int)
    if not ids:
        return jsonify({'success': False, 'error': 'Не вибрано жодного фото'}), 400
    deleted = photo_service.bulk_delete_photos(ids)
    return jsonify({'success': True, 'deleted': deleted})


@photos_bp.route('/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    if not _can_delete():
        abort(403)
    ok, error = photo_service.delete_photo(photo_id)
    if not ok:
        flash(error, 'danger')
    else:
        flash('Фото видалено', 'success')
    order_id = request.form.get('order_id', type=int)
    return redirect(url_for('photos.list_photos', order_id=order_id) if order_id else url_for('photos.list_photos'))
