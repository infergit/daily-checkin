# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)
    
    from app.auth.routes import auth
    from app.checkin.routes import checkin
    from app.models.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(checkin, url_prefix='/checkin')
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app

from flask import render_template
