from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.services.csv_import_service import preview_import, execute_import, preview_import_operational, execute_import_operational, preview_import_kvitkovapovnya, execute_import_kvitkovapovnya

import_csv_bp = Blueprint('import_csv', __name__, url_prefix='/import')


@import_csv_bp.route('/', methods=['GET'])
@login_required
def import_page():
    return render_template('import_csv/index.html')


@import_csv_bp.route('/preview', methods=['POST'])
@login_required
def preview():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не завантажено'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Потрібен файл формату .csv'}), 400

    rows, error = preview_import(file.stream)
    if error:
        return jsonify({'error': error}), 400

    new_count = sum(1 for r in rows if r['client_status'] == 'new')
    existing_count = sum(1 for r in rows if r['client_status'] == 'exists')
    warning_count = sum(1 for r in rows if r['warnings'])

    return jsonify({
        'rows': rows,
        'summary': {
            'total': len(rows),
            'new_clients': new_count,
            'existing_clients': existing_count,
            'warnings': warning_count,
        }
    })


@import_csv_bp.route('/execute', methods=['POST'])
@login_required
def execute():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Немає даних'}), 400

    rows = data.get('rows', [])
    first_delivery_date = data.get('first_delivery_date', '')
    delivery_day = data.get('delivery_day', 'ПН')

    if not rows:
        return jsonify({'error': 'Немає рядків для імпорту'}), 400
    if not first_delivery_date:
        return jsonify({'error': 'Вкажіть дату першої доставки'}), 400

    result = execute_import(rows, first_delivery_date, delivery_day)
    return jsonify(result)


@import_csv_bp.route('/operational', methods=['GET'])
@login_required
def operational_import_page():
    return render_template('import_csv/operational.html')


@import_csv_bp.route('/operational/preview', methods=['POST'])
@login_required
def operational_preview():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не завантажено'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Потрібен файл формату .csv'}), 400

    rows, error = preview_import_operational(file.stream)
    if error:
        return jsonify({'error': error}), 400

    new_count = sum(1 for r in rows if r['client_status'] == 'new')
    existing_count = sum(1 for r in rows if r['client_status'] == 'exists')
    warning_count = sum(1 for r in rows if r['warnings'])
    date_missing = sum(1 for r in rows if not r.get('first_delivery_date'))

    return jsonify({
        'rows': rows,
        'summary': {
            'total': len(rows),
            'new_clients': new_count,
            'existing_clients': existing_count,
            'warnings': warning_count,
            'date_missing': date_missing,
        }
    })


@import_csv_bp.route('/operational/execute', methods=['POST'])
@login_required
def operational_execute():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Немає даних'}), 400

    rows = data.get('rows', [])
    if not rows:
        return jsonify({'error': 'Немає рядків для імпорту'}), 400

    result = execute_import_operational(rows)
    return jsonify(result)


@import_csv_bp.route('/kvitkovapovnya', methods=['GET'])
@login_required
def kvitkovapovnya_import_page():
    return render_template('import_csv/kvitkovapovnya.html')


@import_csv_bp.route('/kvitkovapovnya/preview', methods=['POST'])
@login_required
def kvitkovapovnya_preview():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не завантажено'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Потрібен файл формату .csv'}), 400

    rows, summary = preview_import_kvitkovapovnya(file.stream)
    return jsonify({'rows': rows, 'summary': summary})


@import_csv_bp.route('/kvitkovapovnya/execute', methods=['POST'])
@login_required
def kvitkovapovnya_execute():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Немає даних'}), 400

    rows = data.get('rows', [])
    if not rows:
        return jsonify({'error': 'Немає рядків для імпорту'}), 400

    result = execute_import_kvitkovapovnya(rows)
    return jsonify(result)
