import json
import redis as redis_lib
from flask import current_app

HISTORY_TTL = 259200   # 3 days
PENDING_TTL = 600      # 10 minutes


def _redis():
    return redis_lib.from_url(current_app.config['REDIS_URL'], decode_responses=True)


def get_history(user_id: int) -> list:
    try:
        raw = _redis().get(f'ai_chat_history:{user_id}')
        return json.loads(raw) if raw else []
    except Exception:
        return []


def save_history(user_id: int, messages: list) -> None:
    try:
        _redis().setex(
            f'ai_chat_history:{user_id}',
            HISTORY_TTL,
            json.dumps(messages, ensure_ascii=False)
        )
    except Exception:
        pass


def clear_history(user_id: int) -> None:
    try:
        _redis().delete(f'ai_chat_history:{user_id}')
    except Exception:
        pass


def save_pending_action(user_id: int, action_id: str, action: dict) -> None:
    action['status'] = 'pending'
    try:
        _redis().setex(
            f'ai_pending:{user_id}:{action_id}',
            PENDING_TTL,
            json.dumps(action, ensure_ascii=False)
        )
    except Exception:
        pass


def get_pending_action(user_id: int, action_id: str) -> dict | None:
    try:
        raw = _redis().get(f'ai_pending:{user_id}:{action_id}')
        return json.loads(raw) if raw else None
    except Exception:
        return None


def claim_pending_action(user_id: int, action_id: str) -> bool:
    """
    Atomically transitions pending_action status from 'pending' -> 'executing'.
    Returns True if successfully claimed, False if already claimed/executed/missing.
    """
    key = f'ai_pending:{user_id}:{action_id}'
    r = _redis()
    try:
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(key)
                    raw = pipe.get(key)
                    if not raw:
                        pipe.reset()
                        return False
                    action = json.loads(raw)
                    if action.get('status') != 'pending':
                        pipe.reset()
                        return False
                    action['status'] = 'executing'
                    pipe.multi()
                    pipe.setex(key, PENDING_TTL, json.dumps(action, ensure_ascii=False))
                    pipe.execute()
                    return True
                except redis_lib.WatchError:
                    continue
    except Exception:
        return False


def delete_pending_action(user_id: int, action_id: str) -> None:
    try:
        _redis().delete(f'ai_pending:{user_id}:{action_id}')
    except Exception:
        pass
