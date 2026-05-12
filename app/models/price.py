from app.extensions import db


class Price(db.Model):
    __tablename__ = 'prices'
    id = db.Column(db.Integer, primary_key=True)
    preset_id = db.Column(db.Integer, db.ForeignKey('price_presets.id', ondelete='CASCADE'), nullable=False)
    order_type = db.Column(db.String(20), nullable=False)  # 'one_time' | 'subscription'
    size_id = db.Column(db.Integer, db.ForeignKey('settings.id', ondelete='CASCADE'), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)

    size = db.relationship('Settings', foreign_keys=[size_id])

    __table_args__ = (
        db.UniqueConstraint('preset_id', 'order_type', 'size_id', name='uq_price_preset_type_size'),
    )

    def __repr__(self):
        return f'<Price preset={self.preset_id} type={self.order_type} size={self.size_id} price={self.price}>'
