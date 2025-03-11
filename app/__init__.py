# app/__init__.py
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect  # Add this import
from config import Config
from datetime import timedelta

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()  # Add this line
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Add this line
    
    from app.auth.routes import auth
    from app.checkin.routes import checkin
    from app.projects.routes import projects
    from app.models.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(checkin, url_prefix='/checkin')
    app.register_blueprint(projects, url_prefix='/projects')
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app
