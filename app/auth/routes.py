# app/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.models.models import User
from app.auth.forms import RegistrationForm, LoginForm, UserSettingsForm
from flask_login import login_required

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('checkin.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('checkin.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('checkin.dashboard'))
        else:
            flash('Login unsuccessful. Please check username and password', 'danger')
    
    return render_template('auth/login.html', title='Login', form=form)

@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page"""
    form = UserSettingsForm()
    
    if form.validate_on_submit():
        # Set notification preference
        notification_value = 'Y' if form.receive_checkin_notifications.data else 'N'
        current_user.set_preference('receive_checkin_notifications', notification_value)
        
        # Set Telegram chat ID if provided
        if form.telegram_chat_id.data:
            current_user.set_preference('telegram_chat_id', form.telegram_chat_id.data)
        
        flash('Your settings have been updated!', 'success')
        return redirect(url_for('auth.settings'))
    elif request.method == 'GET':
        # Set form defaults from current preferences
        form.receive_checkin_notifications.data = current_user.get_preference('receive_checkin_notifications', 'N') == 'Y'
        form.telegram_chat_id.data = current_user.get_preference('telegram_chat_id')
    
    return render_template('auth/settings.html', title='User Settings', form=form)
