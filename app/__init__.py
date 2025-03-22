# app/__init__.py
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect  # Add this import
from config import Config
from datetime import timedelta
import time
# Remove these imports since we're not using them yet
# from app.utils.telegram_bot import configure_telegram_bot
# import threading

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
    from app.friends.routes import friends as friends_bp  # Add this line
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(checkin, url_prefix='/checkin')
    app.register_blueprint(projects, url_prefix='/projects')
    app.register_blueprint(friends_bp, url_prefix='/friends')  # Add this line
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.context_processor
    def inject_asset_version():
        # Get last modified time of main.js
        try:
            js_mtime = os.path.getmtime('app/static/js/main.js')
            css_mtime = os.path.getmtime('app/static/css/main.css')
            version = int(max(js_mtime, css_mtime))  # Use the latest modification time
        except OSError:
            version = int(time.time())  # Fallback to current time
            
        return {'asset_version': version}
    
    @app.template_global()
    def get_pending_join_request_count(project_id):
        from app.models.models import ProjectJoinRequest
        return ProjectJoinRequest.query.filter_by(
            project_id=project_id,
            status='pending'
        ).count()
    
    @app.template_global()
    def to_user_timezone(utc_dt):
        """Convert UTC datetime to user's timezone"""
        from app.utils.timezone import to_user_timezone as convert_timezone
        return convert_timezone(utc_dt)
    
    # Remove the Telegram bot configuration for now
    # if not app.debug:
    #     bot = configure_telegram_bot(app)
    #     if bot:
    #         threading.Thread(target=bot.polling, kwargs={'none_stop': True}).start()
    
    return app
