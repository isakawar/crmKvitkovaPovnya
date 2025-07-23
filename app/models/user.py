from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

# Константи для ролей
ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'

# Права доступу для ролей
ROLE_PERMISSIONS = {
    ROLE_ADMIN: [
        'view_orders', 'edit_orders', 'delete_orders',
        'view_clients', 'edit_clients', 'delete_clients',
        'view_couriers', 'edit_couriers', 'delete_couriers',
        'view_deliveries', 'edit_deliveries', 'delete_deliveries',
        'view_distribution', 'edit_distribution',
        'view_reports',
        'view_settings', 'edit_settings'
    ],
    ROLE_MANAGER: [
        'view_orders', 'edit_orders', 'delete_orders',
        'view_clients', 'edit_clients', 'delete_clients',
        'view_couriers', 'edit_couriers', 'delete_couriers',
        'view_deliveries', 'edit_deliveries', 'delete_deliveries',
        'view_distribution', 'edit_distribution'
    ]
}

# Association table for user roles
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    user_type = db.Column(db.String(20))  # 'courier', 'client', 'admin', 'manager'
    
    # Relationships
    roles = db.relationship('Role', secondary=user_roles, lazy='subquery',
                          backref=db.backref('users', lazy=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        return any(role.name == role_name for role in self.roles)
    
    def has_permission(self, permission):
        """Перевіряє чи має користувач певний дозвіл"""
        user_permissions = set()
        for role in self.roles:
            if role.name in ROLE_PERMISSIONS:
                user_permissions.update(ROLE_PERMISSIONS[role.name])
        return permission in user_permissions

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    @staticmethod
    def get_permissions(role_name):
        """Повертає список дозволів для ролі"""
        return ROLE_PERMISSIONS.get(role_name, []) 