import os
import uuid
from flask import current_app
from app.extensions import db
from app.models import OrderPhoto


def _allowed(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config.get('ALLOWED_PHOTO_EXTENSIONS', set())


def save_photo(file, order_id, uploaded_by_id, comment=None):
    if not file or not file.filename:
        return None, 'Файл не вибрано'
    if not _allowed(file.filename):
        return None, 'Недозволений формат файлу'

    ext = file.filename.rsplit('.', 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))

    photo = OrderPhoto(
        order_id=order_id,
        filename=filename,
        original_name=file.filename,
        uploaded_by=uploaded_by_id,
        comment=comment or None,
    )
    db.session.add(photo)
    db.session.commit()
    return photo, None


def get_photos_for_order(order_id):
    return OrderPhoto.query.filter_by(order_id=order_id).order_by(OrderPhoto.created_at.desc()).all()


def get_all_photos(page=1, per_page=20, order_id=None):
    q = OrderPhoto.query
    if order_id:
        q = q.filter_by(order_id=order_id)
    return q.order_by(OrderPhoto.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)


def get_photo_by_id(photo_id):
    return OrderPhoto.query.get(photo_id)


def delete_photo(photo_id):
    photo = get_photo_by_id(photo_id)
    if not photo:
        return False, 'Фото не знайдено'
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], photo.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(photo)
    db.session.commit()
    return True, None
