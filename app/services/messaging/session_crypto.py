"""Encrypt/decrypt secrets stored at rest in the database.

Used for MTProto session strings (`telegram_personal` channels) — unlike the
bot/Instagram adapters, whose only secret is an env-var token, a personal
Telegram login must persist a session string in the DB, and that string is
bearer-equivalent to full access to the account. Key comes from
`MESSAGING_SESSION_KEY` (Fernet, base64), never stored alongside the data.
"""
from __future__ import annotations

from cryptography.fernet import Fernet
from flask import current_app


def _fernet() -> Fernet:
    key = current_app.config.get('MESSAGING_SESSION_KEY')
    if not key:
        raise RuntimeError('MESSAGING_SESSION_KEY не налаштовано — неможливо шифрувати/розшифрувати сесію')
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
