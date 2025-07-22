from marshmallow import Schema, fields, ValidationError, validates, validates_schema
from marshmallow.validate import Length, OneOf
import re
from datetime import date

class OrderSchema(Schema):
    """Схема для валідації даних замовлення"""
    
    # Основні поля
    client_instagram = fields.Str(required=True, validate=Length(min=1, max=100))
    recipient_name = fields.Str(required=True, validate=Length(min=2, max=100))
    recipient_phone = fields.Str(required=True)
    recipient_social = fields.Str(allow_none=True, validate=Length(max=128))
    
    # Адреса
    city = fields.Str(required=True, validate=Length(min=1, max=64))
    street = fields.Str(allow_none=True, validate=Length(min=1, max=128))
    building_number = fields.Str(allow_none=True, validate=Length(max=32))
    floor = fields.Str(allow_none=True, validate=Length(max=16))
    entrance = fields.Str(allow_none=True, validate=Length(max=16))
    is_pickup = fields.Bool(load_default=False)
    
    # Доставка
    delivery_type = fields.Str(
        required=True, 
        validate=OneOf(['Weekly', 'Monthly', 'Bi-weekly', 'One-time'])
    )
    size = fields.Str(
        required=True, 
        validate=OneOf(['M', 'L', 'XL', 'XXL', 'Власний'])
    )
    custom_amount = fields.Int(allow_none=True, missing=None)
    
    # Дати та час
    first_delivery_date = fields.Date(required=True)
    delivery_day = fields.Str(
        required=True, 
        validate=OneOf(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'НД'])
    )
    time_from = fields.Str(allow_none=True, validate=Length(max=8))
    time_to = fields.Str(allow_none=True, validate=Length(max=8))
    
    # Додаткова інформація
    comment = fields.Str(allow_none=True)
    preferences = fields.Str(allow_none=True)
    for_whom = fields.Str(required=True, validate=Length(min=1, max=64))
    
    @validates('recipient_phone')
    def validate_phone(self, value, **kwargs):
        """Валідує український номер телефону"""
        pattern = r'^\+380[0-9]{9}$'
        if not re.match(pattern, value):
            raise ValidationError('Телефон має бути у форматі +380XXXXXXXXX')
        return value
    
    @validates('client_instagram')
    def validate_instagram(self, value, **kwargs):
        """Валідує Instagram username"""
        pattern = r'^[a-zA-Z0-9._]{1,30}$'
        if not re.match(pattern, value):
            raise ValidationError('Некорректний Instagram username')
        return value
    
    @validates('first_delivery_date')
    def validate_delivery_date(self, value, **kwargs):
        """Валідує дату доставки"""
        if value < date.today():
            raise ValidationError('Дата доставки не може бути в минулому')
        return value
    
    @validates('custom_amount')
    def validate_custom_amount(self, value, **kwargs):
        """Валідує суму для власного розміру"""
        # Якщо значення порожнє або None, повертаємо None
        if value == "" or value is None:
            return None
        # Якщо значення не є числом або менше/дорівнює 0
        try:
            amount = int(value)
            if amount <= 0:
                raise ValidationError('Сума має бути більше 0')
            return amount
        except (ValueError, TypeError):
            raise ValidationError('Сума має бути цілим числом')
    
    @validates_schema
    def validate_street_pickup(self, data, **kwargs):
        is_pickup = data.get('is_pickup', False)
        street = data.get('street')
        if not is_pickup and (not street or street.strip() == ''):
            raise ValidationError({'street': 'Вулиця обов\'язкова для доставки'})
    
    @validates_schema
    def validate_custom_amount_required(self, data, **kwargs):
        """Перевіряє, чи вказана сума для власного розміру"""
        size = data.get('size')
        custom_amount = data.get('custom_amount')
        
        if size == 'Власний':
            if custom_amount is None or custom_amount == "" or custom_amount <= 0:
                raise ValidationError({'custom_amount': 'Для власного розміру потрібно вказати суму більше 0'})

class OrderUpdateSchema(OrderSchema):
    """Схема для оновлення замовлення (часткова валідація)"""
    
    class Meta:
        unknown = True  # Дозволяє додаткові поля
    
    # Робимо всі поля необов'язковими для оновлення
    client_instagram = fields.Str(validate=Length(min=1, max=100))
    recipient_name = fields.Str(validate=Length(min=2, max=100))
    recipient_phone = fields.Str()
    city = fields.Str(validate=Length(min=1, max=64))
    street = fields.Str(validate=Length(min=1, max=128))
    delivery_type = fields.Str(validate=OneOf(['Weekly', 'Monthly', 'Bi-weekly', 'One-time']))
    size = fields.Str(validate=OneOf(['M', 'L', 'XL', 'XXL', 'Власний']))
    first_delivery_date = fields.Date()
    delivery_day = fields.Str(validate=OneOf(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'НД']))
    for_whom = fields.Str(validate=Length(min=1, max=64)) 