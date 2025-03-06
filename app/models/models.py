# app/models/models.py
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    date_registered = db.Column(db.DateTime, default=datetime.utcnow)
    checkins = db.relationship('CheckIn', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    check_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    check_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    note = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<CheckIn {self.user.username} on {self.check_date}>'
