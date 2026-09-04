from cryptography.fernet import Fernet

from app.services.messaging import session_crypto


def test_encrypt_decrypt_roundtrip(app):
    app.config['MESSAGING_SESSION_KEY'] = Fernet.generate_key().decode()
    plain = 'super-secret-mtproto-session-string'
    encrypted = session_crypto.encrypt(plain)
    assert encrypted != plain
    assert session_crypto.decrypt(encrypted) == plain


def test_encrypt_raises_without_key(app):
    app.config['MESSAGING_SESSION_KEY'] = ''
    try:
        session_crypto.encrypt('x')
        assert False, 'expected RuntimeError'
    except RuntimeError:
        pass
