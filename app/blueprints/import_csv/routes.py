from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.services.csv_import_service import preview_import_kvitkovapovnya, execute_import_kvitkovapovnya

import_csv_bp = Blueprint('import_csv', __name__, url_prefix='/import')


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
