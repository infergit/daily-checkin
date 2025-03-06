# app/checkin/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models.models import CheckIn
from app.checkin.forms import CheckInForm

checkin = Blueprint('checkin', __name__)

@checkin.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    form = CheckInForm()
    
    # Check if user already checked in today
    today = date.today()
    today_checkin = CheckIn.query.filter_by(
        user_id=current_user.id,
        check_date=today
    ).first()
    
    if form.validate_on_submit():
        if today_checkin:
            flash('You have already checked in today!', 'info')
        else:
            checkin = CheckIn(
                user_id=current_user.id,
                note=form.note.data
            )
            db.session.add(checkin)
            db.session.commit()
            flash('Check-in successful!', 'success')
            return redirect(url_for('checkin.dashboard'))
    
    # Get recent check-ins (last 7 days)
    recent_checkins = CheckIn.query.filter_by(
        user_id=current_user.id
    ).order_by(CheckIn.check_date.desc()).limit(7).all()
    
    return render_template(
        'checkin/dashboard.html',
        title='Dashboard',
        form=form,
        already_checked_in=bool(today_checkin),
        recent_checkins=recent_checkins
    )

@checkin.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    checkins = CheckIn.query.filter_by(
        user_id=current_user.id
    ).order_by(CheckIn.check_date.desc()).paginate(page=page, per_page=10)
    
    return render_template(
        'checkin/history.html',
        title='Check-in History',
        checkins=checkins
    )
