from app.extensions import db


class Price(db.Model):
    __tablename__ = 'prices'
    id = db.Column(db.Integer, primary_key=True)
    subscription_type_id = db.Column(db.Integer, db.ForeignKey('settings.id', ondelete='CASCADE'), nullable=False)
    size_id = db.Column(db.Integer, db.ForeignKey('settings.id', ondelete='CASCADE'), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)

    subscription_type = db.relationship('Settings', foreign_keys=[subscription_type_id])
    size = db.relationship('Settings', foreign_keys=[size_id])

    __table_args__ = (
        db.UniqueConstraint('subscription_type_id', 'size_id', name='uq_price_sub_size'),
    )

    def __repr__(self):
        return f'<Price sub={self.subscription_type_id} size={self.size_id} price={self.price}>'
