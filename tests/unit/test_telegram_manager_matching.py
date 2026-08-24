from app.models.user import User


def test_find_manager_by_phone_matches_active_admin_or_manager(session):
    from app.telegram_bot.services import find_manager_by_phone

    manager = User(username='findme', email='findme@example.com', user_type='manager',
                    phone='+380661112233', is_active=True)
    manager.set_password('x')
    session.add(manager)
    session.commit()

    found = find_manager_by_phone('+380661112233')
    assert found is not None
    assert found.id == manager.id


def test_find_manager_by_phone_ignores_inactive_or_wrong_role(session):
    from app.telegram_bot.services import find_manager_by_phone

    inactive = User(username='inactive1', email='inactive1@example.com', user_type='manager',
                     phone='+380662223344', is_active=False)
    inactive.set_password('x')
    florist = User(username='florist1', email='florist1@example.com', user_type='florist',
                    phone='+380663334455', is_active=True)
    florist.set_password('x')
    session.add_all([inactive, florist])
    session.commit()

    assert find_manager_by_phone('+380662223344') is None
    assert find_manager_by_phone('+380663334455') is None
    assert find_manager_by_phone('+380000000000') is None
