from app.extensions import db

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False, index=True)
    value = db.Column(db.String(100), nullable=False, index=True)

    def __repr__(self):
        return f'<Settings {self.type}: {self.value}>' 