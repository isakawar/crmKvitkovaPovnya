from flask import request, jsonify
from flask_login import login_required, current_user

from app.blueprints.ai_agent import ai_agent_bp
from app.services.ai_agent_service import (
    run_agent_turn,
    validate_before_execute,
    execute_confirmed_action,
    write_audit_log,
)
from app.services.redis_chat_service import (
    get_history,
    claim_pending_action,
    get_pending_action,
    delete_pending_action,
    clear_history,
)

ALLOWED_ROLES = {'admin', 'manager'}


def _check_role():
    if current_user.user_type not in ALLOWED_ROLES:
        return jsonify({'error': 'Доступ заборонено'}), 403
    return None


@ai_agent_bp.route('/ai/chat', methods=['POST'])
@login_required
def chat():
    denied = _check_role()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Порожнє повідомлення'}), 400

    result = run_agent_turn(message, current_user.id)
    return jsonify(result)


@ai_agent_bp.route('/ai/confirm', methods=['POST'])
@login_required
def confirm():
    denied = _check_role()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    action_id = data.get('action_id', '').strip()
    confirmed = data.get('confirmed', False)

    if not action_id:
        return jsonify({'error': 'action_id відсутній'}), 400

    # Read action first, then atomically claim it
    action = get_pending_action(current_user.id, action_id)
    if not action:
        return jsonify({'success': False, 'reply': 'Дія не знайдена або протермінована.'}), 404

    # Idempotency: atomically transition status pending -> executing
    if not claim_pending_action(current_user.id, action_id):
        return jsonify({'success': False, 'reply': 'Цю дію вже виконано або вона застаріла.'}), 409

    if not confirmed:
        write_audit_log(current_user.id, action, status='cancelled')
        delete_pending_action(current_user.id, action_id)
        return jsonify({'success': True, 'reply': 'Дію скасовано.'})

    # Validate before execute
    errors = validate_before_execute(action)
    if errors:
        write_audit_log(current_user.id, action, status='validation_error',
                        error_msg='; '.join(errors))
        delete_pending_action(current_user.id, action_id)
        return jsonify({'success': False, 'reply': 'Не вдалося виконати: ' + '; '.join(errors)})

    # Execute
    success, reply, after_data = execute_confirmed_action(action, current_user.id)
    status = 'executed' if success else 'failed'
    write_audit_log(current_user.id, action, status=status,
                    after_data=after_data,
                    error_msg=None if success else reply)
    delete_pending_action(current_user.id, action_id)

    return jsonify({'success': success, 'reply': reply})


@ai_agent_bp.route('/ai/history', methods=['GET'])
@login_required
def history():
    denied = _check_role()
    if denied:
        return denied

    messages = get_history(current_user.id)
    # Return only user/assistant messages (skip tool messages)
    visible = [
        {'role': m['role'], 'content': m.get('content') or ''}
        for m in messages
        if m.get('role') in ('user', 'assistant') and m.get('content')
    ]
    return jsonify({'messages': visible[-50:]})


@ai_agent_bp.route('/ai/clear', methods=['POST'])
@login_required
def clear():
    denied = _check_role()
    if denied:
        return denied

    clear_history(current_user.id)
    return jsonify({'success': True})
