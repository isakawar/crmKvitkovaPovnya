"""
Tests for app/models/user.py

Covers:
- User password hashing and verification
- User role assignment and has_role()
- User has_permission() for admin/manager roles
- Role.get_permissions()
- User active status
"""
import pytest
from app.models.user import User, Role, ROLE_ADMIN, ROLE_MANAGER, ROLE_PERMISSIONS


def _make_user(session, email='test@test.com', username='testuser', is_active=True, roles=None):
    u = User(email=email, username=username, is_active=is_active)
    u.set_password('secret123')
    if roles:
        for role in roles:
            u.roles.append(role)
    session.add(u)
    session.commit()
    return u


def _make_role(session, name):
    r = Role(name=name)
    session.add(r)
    session.commit()
    return r


# ── Password hashing ─────────────────────────────────────────────────────────

def test_set_password_hashes_the_password(session):
    user = User(email='a@b.com', username='u1')
    user.set_password('mysecret')
    assert user.password_hash != 'mysecret'
    assert user.password_hash is not None


def test_check_password_correct(session):
    user = User(email='a@b.com', username='u1')
    user.set_password('mysecret')
    assert user.check_password('mysecret') is True


def test_check_password_incorrect(session):
    user = User(email='a@b.com', username='u1')
    user.set_password('mysecret')
    assert user.check_password('wrong') is False


def test_check_password_case_sensitive(session):
    user = User(email='a@b.com', username='u1')
    user.set_password('MySecret')
    assert user.check_password('mysecret') is False


# ── User active status ───────────────────────────────────────────────────────

def test_user_is_active_by_default(session):
    user = User(email='a@b.com', username='u1')
    user.set_password('x')
    session.add(user)
    session.commit()
    assert user.is_active is True


def test_user_can_be_deactivated(session):
    user = _make_user(session, email='deact@test.com', username='deact', is_active=False)
    assert user.is_active is False


# ── Role assignment ──────────────────────────────────────────────────────────

def test_has_role_returns_true_when_assigned(session):
    role = _make_role(session, ROLE_ADMIN)
    user = _make_user(session, email='r1@test.com', username='r1', roles=[role])
    assert user.has_role(ROLE_ADMIN) is True


def test_has_role_returns_false_when_not_assigned(session):
    role = _make_role(session, ROLE_ADMIN)
    user = _make_user(session, email='r2@test.com', username='r2', roles=[])
    assert user.has_role(ROLE_ADMIN) is False


def test_user_can_have_multiple_roles(session):
    admin_role = _make_role(session, ROLE_ADMIN)
    manager_role = _make_role(session, ROLE_MANAGER)
    user = _make_user(session, email='r3@test.com', username='r3', roles=[admin_role, manager_role])
    assert user.has_role(ROLE_ADMIN) is True
    assert user.has_role(ROLE_MANAGER) is True


# ── Permissions ──────────────────────────────────────────────────────────────

def test_admin_has_all_admin_permissions(session):
    role = _make_role(session, ROLE_ADMIN)
    user = _make_user(session, email='p1@test.com', username='p1', roles=[role])
    for perm in ROLE_PERMISSIONS[ROLE_ADMIN]:
        assert user.has_permission(perm) is True


def test_manager_has_manager_permissions(session):
    role = _make_role(session, ROLE_MANAGER)
    user = _make_user(session, email='p2@test.com', username='p2', roles=[role])
    for perm in ROLE_PERMISSIONS[ROLE_MANAGER]:
        assert user.has_permission(perm) is True


def test_manager_does_not_have_admin_only_permissions(session):
    role = _make_role(session, ROLE_MANAGER)
    user = _make_user(session, email='p3@test.com', username='p3', roles=[role])
    admin_only = set(ROLE_PERMISSIONS[ROLE_ADMIN]) - set(ROLE_PERMISSIONS[ROLE_MANAGER])
    for perm in admin_only:
        assert user.has_permission(perm) is False


def test_user_without_roles_has_no_permissions(session):
    user = _make_user(session, email='p4@test.com', username='p4', roles=[])
    assert user.has_permission('view_orders') is False
    assert user.has_permission('edit_settings') is False


def test_user_with_multiple_roles_has_combined_permissions(session):
    admin_role = _make_role(session, ROLE_ADMIN)
    manager_role = _make_role(session, ROLE_MANAGER)
    user = _make_user(session, email='p5@test.com', username='p5', roles=[admin_role, manager_role])
    all_perms = set(ROLE_PERMISSIONS[ROLE_ADMIN]) | set(ROLE_PERMISSIONS[ROLE_MANAGER])
    for perm in all_perms:
        assert user.has_permission(perm) is True


def test_has_permission_unknown_permission_returns_false(session):
    role = _make_role(session, ROLE_ADMIN)
    user = _make_user(session, email='p6@test.com', username='p6', roles=[role])
    assert user.has_permission('nonexistent_perm') is False


# ── Role.get_permissions() ──────────────────────────────────────────────────

def test_role_get_permissions_returns_list_for_admin():
    perms = Role.get_permissions(ROLE_ADMIN)
    assert isinstance(perms, list)
    assert 'view_orders' in perms
    assert 'edit_settings' in perms


def test_role_get_permissions_returns_list_for_manager():
    perms = Role.get_permissions(ROLE_MANAGER)
    assert isinstance(perms, list)
    assert 'view_orders' in perms
    assert 'edit_settings' not in perms


def test_role_get_permissions_unknown_role_returns_empty_list():
    assert Role.get_permissions('unknown') == []
