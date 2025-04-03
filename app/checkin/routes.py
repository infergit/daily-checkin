# app/checkin/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta  # 添加 timedelta 导入
from app import db
from app.services.s3_service import S3Service  # Import S3Service class
from app.models.models import CheckIn, Project, ProjectMember, ProjectStat, UserProjectStat, User, FriendRelationship, CheckInImage  # 添加 CheckInImage
from app.checkin.forms import CheckInForm, ProjectSelectForm
from app.utils.timezone import get_user_timezone, to_user_timezone
import pytz
from app.utils.telegram_utils import notify_friends_of_checkin  # Import the notification function

checkin = Blueprint('checkin', __name__)

@checkin.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # 获取用户可参与的项目
    projects = db.session.query(Project).join(
        ProjectMember, Project.id == ProjectMember.project_id
    ).filter(
        ProjectMember.user_id == current_user.id
    ).all()
    
    if not projects:
        flash('You need to join or create a project first.', 'info')
        return redirect(url_for('projects.list_projects'))
    
    # get project_id from request or get the default project
    project_id = request.args.get('project', type=int)
    if project_id is None:
        default_project_id = current_user.get_preference('default_project_id', '')
        if (default_project_id):
            project_id = int(default_project_id)

    if project_id is None and projects:
        project_id = projects[0].id
    
    project = next((p for p in projects if p.id == project_id), None) if project_id else None
    
    if not project:
        flash('Project not found or you don\'t have access.', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    project_select_form = ProjectSelectForm()
    project_select_form.project.choices = [(p.id, p.name) for p in projects]
    if project_id:
        project_select_form.project.default = project_id
        project_select_form.process()
    
    form = CheckInForm()
    
    # Get current time in UTC and user's local timezone
    now_utc = datetime.now(pytz.UTC)
    local_now = to_user_timezone(now_utc)
    user_today = local_now.date()  # Get the user's local date

    # Find check-ins from the user's "today" in UTC time
    # First get the start and end of the user's day in their timezone
    start_of_day_local = datetime.combine(user_today, datetime.min.time())
    end_of_day_local = datetime.combine(user_today, datetime.max.time())

    # Convert these times to UTC for the database query
    user_tz = get_user_timezone()
    start_of_day_utc = user_tz.localize(start_of_day_local).astimezone(pytz.UTC)
    end_of_day_utc = user_tz.localize(end_of_day_local).astimezone(pytz.UTC)

    # Query using the UTC time range that corresponds to the user's local day
    today_checkin = CheckIn.query.filter(
        CheckIn.user_id == current_user.id,
        CheckIn.project_id == project.id,
        CheckIn.check_time >= start_of_day_utc,
        CheckIn.check_time <= end_of_day_utc
    ).first()
    
    if form.validate_on_submit() and request.method == 'POST':
        if project.frequency_type == 'daily' and today_checkin:
            flash('You have already checked in today for this project!', 'info')
        else:
            checkin = CheckIn(
                user_id=current_user.id,
                project_id=project.id,
                check_date=now_utc.date(),  # Store UTC date
                check_time=now_utc,
                note=form.note.data,
                location=None  # 可以在后续版本中添加位置功能
            )
            db.session.add(checkin)
            db.session.commit()

            # Notify friends (after successful database commit)
            try:
                notify_friends_of_checkin(current_user, project, checkin)
            except Exception as e:
                # Log error but don't interrupt the check-in process
                current_app.logger.error(f"Failed to send check-in notifications: {str(e)}")

            # 更新项目统计
            update_project_stats(project.id)
            # 更新用户项目统计 - pass UTC date
            update_user_project_stats(current_user.id, project.id, now_utc.date())
            
            db.session.commit()
            flash('Check-in successful!', 'success')
            return redirect(url_for('checkin.dashboard', project=project.id))
    
    # Get recent check-ins for this project (last 7 days)
    recent_checkins = CheckIn.query.filter_by(
        user_id=current_user.id,
        project_id=project.id
    ).order_by(CheckIn.check_date.desc(), CheckIn.check_time.desc()).limit(7).all()
    
    # 获取用户在该项目的统计数据
    user_stats = UserProjectStat.query.filter_by(
        user_id=current_user.id,
        project_id=project.id
    ).first()
    
    if not user_stats:
        user_stats = UserProjectStat(
            user_id=current_user.id,
            project_id=project.id
        )
        db.session.add(user_stats)
        db.session.commit()
    
    # Convert UTC times to local times before passing to template
    for checkin in recent_checkins:
        # Convert check_time to local time
        checkin.check_time = to_user_timezone(checkin.check_time)
        # Add display_date attribute for template use
        checkin.display_date = to_user_timezone(
            datetime.combine(checkin.check_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
        ).date()
    
    # Create S3 service for the template
    from app.services.s3_service import S3Service
    s3_service = S3Service()
    
    return render_template(
        'checkin/dashboard.html',
        title='Dashboard',
        form=form,
        project_select_form=project_select_form,
        already_checked_in=bool(today_checkin) if project.frequency_type == 'daily' else False,
        recent_checkins=recent_checkins,
        project=project,
        projects=projects,
        user_stats=user_stats,
        s3_service=s3_service
    )

@checkin.route('/history')
@login_required
def history():
    """Display check-in history with dual privacy protection"""
    project_id = request.args.get('project', type=int)
    
    # Get user's projects
    projects = db.session.query(Project).join(
        ProjectMember, Project.id == ProjectMember.project_id
    ).filter(
        ProjectMember.user_id == current_user.id
    ).all()
    
    if project_id is None and projects:
        project_id = projects[0].id
    
    project = next((p for p in projects if p.id == project_id), None) if project_id else None
    
    if not project:
        flash('Project not found or you don\'t have access.', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    # Prepare project selector form
    project_select_form = ProjectSelectForm()
    project_select_form.project.choices = [(p.id, p.name) for p in projects]
    if project_id:
        project_select_form.project.default = project_id
        project_select_form.process()
    
    # Get view mode from request
    view_mode = request.args.get('view', 'all')
    if view_mode not in ['all', 'mine']:
        view_mode = 'all'
    
    # Build the check-ins query
    if view_mode == 'mine':
        # Only show current user's check-ins
        checkins_query = db.session.query(
            CheckIn, User.username
        ).join(
            User, CheckIn.user_id == User.id
        ).filter(
            CheckIn.project_id == project.id,
            CheckIn.user_id == current_user.id
        )
    else:
        # Show all visible check-ins based on dual privacy protection
        
        # First, get all project members who are also friends with the current user
        project_members = db.session.query(
            ProjectMember.user_id
        ).filter(
            ProjectMember.project_id == project.id
        ).all()
        project_member_ids = [m.user_id for m in project_members]
        
        # Get all friend IDs
        friend_ids = []
        # Friends where current user is the requester
        requester_friends = db.session.query(
            FriendRelationship.addressee_id
        ).filter(
            FriendRelationship.requester_id == current_user.id,
            FriendRelationship.status == 'accepted'
        ).all()
        friend_ids.extend([f.addressee_id for f in requester_friends])
        
        # Friends where current user is the addressee
        addressee_friends = db.session.query(
            FriendRelationship.requester_id
        ).filter(
            FriendRelationship.addressee_id == current_user.id,
            FriendRelationship.status == 'accepted'
        ).all()
        friend_ids.extend([f.requester_id for f in addressee_friends])
        
        # Filter for users who are both project members and friends with current user
        visible_user_ids = [uid for uid in project_member_ids if uid in friend_ids]
        
        # Always include current user's own check-ins
        visible_user_ids.append(current_user.id)
        
        # Now query check-ins from visible users
        checkins_query = db.session.query(
            CheckIn, User.username
        ).join(
            User, CheckIn.user_id == User.id
        ).filter(
            CheckIn.project_id == project.id,
            CheckIn.user_id.in_(visible_user_ids)
        )
    
    # Order by date and time, descending
    checkins_query = checkins_query.order_by(
        CheckIn.check_date.desc(), 
        CheckIn.check_time.desc()
    )
    
    # Paginate results
    page = request.args.get('page', 1, type=int)
    checkins = checkins_query.paginate(
        page=page, 
        per_page=10,
        error_out=False
    )
    
    # Get project stats
    project_stats = ProjectStat.query.filter_by(project_id=project.id).first()
    
    # Convert UTC times to local times before passing to template
    for checkin_tuple in checkins.items:
        checkin = checkin_tuple[0]  # Because this returns a (CheckIn, username) tuple
        # Convert check_time to local time
        checkin.check_time = to_user_timezone(checkin.check_time)
        # Add display_date attribute for template use
        checkin.display_date = to_user_timezone(
            datetime.combine(checkin.check_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
        ).date()
    
    # Create S3 service for the template
    from app.services.s3_service import S3Service
    s3_service = S3Service()
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'html': render_template('checkin/partials/history_table.html', 
                                   checkins=checkins,
                                   view_mode=view_mode,
                                   project=project,
                                   s3_service=s3_service)
        })
    
    return render_template(
        'checkin/history.html',
        title='Check-in History',
        project=project,
        project_select_form=project_select_form,
        checkins=checkins,
        view_mode=view_mode,
        project_stats=project_stats,
        s3_service=s3_service
    )

@checkin.route('/delete_checkin/<int:checkin_id>', methods=['POST'])
@login_required
def delete_checkin(checkin_id):
    # Get the check-in record
    checkin = CheckIn.query.get_or_404(checkin_id)
    
    # Verify that the check-in belongs to the current user
    if checkin.user_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You do not have permission to delete this check-in.'})
        flash('You do not have permission to delete this check-in.', 'danger')
        return redirect(url_for('checkin.history'))
    
    # Store project_id before deleting the record
    project_id = checkin.project_id
    
    # Delete the check-in
    db.session.delete(checkin)
    
    # Update project statistics
    update_project_stats(project_id)
    
    # Update user project statistics
    # Get all remaining check-ins for this user in this project
    user_checkins = CheckIn.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).order_by(CheckIn.check_date).all()
    
    # Reset stats
    user_stats = UserProjectStat.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first()
    
    if user_stats:
        user_stats.total_checkins = len(user_checkins)
        
        # Recalculate streak from scratch
        current_streak = 0
        highest_streak = 0
        last_date = None
        
        for check in user_checkins:
            if not last_date or (check.check_date - last_date).days == 1:
                current_streak += 1
            elif last_date and check.check_date == last_date:
                # Same day check-in, don't increment streak
                pass
            else:
                # Streak broken
                current_streak = 1
            
            highest_streak = max(highest_streak, current_streak)
            last_date = check.check_date
        
        user_stats.current_streak = current_streak
        user_stats.highest_streak = highest_streak
        user_stats.last_checkin_date = last_date if user_checkins else None
    
    db.session.commit()
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True, 
            'message': 'Check-in record has been deleted.',
            'dashboardUrl': url_for('checkin.dashboard', project=project_id)
        })
    
    flash('Check-in record has been deleted.', 'success')
    return redirect(url_for('checkin.history', project=project_id))

@checkin.route('/api/checkins')
@login_required
def api_checkins():
    """API endpoint to get check-ins with privacy controls"""
    project_id = request.args.get('project', type=int)
    
    # Validate project access
    project = Project.query.get_or_404(project_id)
    is_member = ProjectMember.query.filter_by(
        project_id=project_id, 
        user_id=current_user.id
    ).first() is not None
    
    if not is_member:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get view mode from request
    view_mode = request.args.get('view', 'all')
    if view_mode not in ['all', 'mine']:
        view_mode = 'all'
    
    # Build the check-ins query
    if view_mode == 'mine':
        # Only show current user's check-ins
        checkins_query = db.session.query(
            CheckIn, User.username
        ).join(
            User, CheckIn.user_id == User.id
        ).filter(
            CheckIn.project_id == project.id,
            CheckIn.user_id == current_user.id
        )
    else:
        # Show all visible check-ins based on dual privacy protection
        
        # First, get all project members who are also friends with the current user
        project_members = db.session.query(
            ProjectMember.user_id
        ).filter(
            ProjectMember.project_id == project.id
        ).all()
        project_member_ids = [m.user_id for m in project_members]
        
        # Get all friend IDs
        friend_ids = []
        # Friends where current user is the requester
        requester_friends = db.session.query(
            FriendRelationship.addressee_id
        ).filter(
            FriendRelationship.requester_id == current_user.id,
            FriendRelationship.status == 'accepted'
        ).all()
        friend_ids.extend([f.addressee_id for f in requester_friends])
        
        # Friends where current user is the addressee
        addressee_friends = db.session.query(
            FriendRelationship.requester_id
        ).filter(
            FriendRelationship.addressee_id == current_user.id,
            FriendRelationship.status == 'accepted'
        ).all()
        friend_ids.extend([f.requester_id for f in addressee_friends])
        
        # Filter for users who are both project members and friends with current user
        visible_user_ids = [uid for uid in project_member_ids if uid in friend_ids]
        
        # Always include current user's own check-ins
        visible_user_ids.append(current_user.id)
        
        # Now query check-ins from visible users
        checkins_query = db.session.query(
            CheckIn, User.username
        ).join(
            User, CheckIn.user_id == User.id
        ).filter(
            CheckIn.project_id == project.id,
            CheckIn.user_id.in_(visible_user_ids)
        )
    
    # Order by date and time, descending
    checkins_query = checkins_query.order_by(
        CheckIn.check_date.desc(), 
        CheckIn.check_time.desc()
    )
    
    # Optional pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    pagination = checkins_query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format data for response
    result = []
    for checkin, username in pagination.items:
        result.append({
            'id': checkin.id,
            'user_id': checkin.user_id,
            'username': username,
            'date': checkin.check_date.strftime('%Y-%m-%d'),
            'time': checkin.check_time.strftime('%H:%M'),
            'note': checkin.note,
            'location': checkin.location,
            'is_self': checkin.user_id == current_user.id
        })
    
    return jsonify({
        'checkins': result,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })

@checkin.route('/checkin/<int:checkin_id>')
@login_required
def view_checkin(checkin_id):
    """View a specific check-in record with privacy checks"""
    checkin = CheckIn.query.get_or_404(checkin_id)
    
    # Verify permission to view this check-in
    if not can_view_checkin(current_user.id, checkin.user_id, checkin.project_id):
        flash('You do not have permission to view this check-in.', 'danger')
        return redirect(url_for('checkin.dashboard'))
    
    # Convert check_time to local time
    checkin.check_time = to_user_timezone(checkin.check_time)
    # Add display_date attribute for template use
    checkin.display_date = to_user_timezone(
        datetime.combine(checkin.check_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
    ).date()
    
    # Get project details
    project = Project.query.get(checkin.project_id)
    
    # Create S3 service for the template
    from app.services.s3_service import S3Service
    s3_service = S3Service()
    
    return render_template(
        'checkin/view_checkin.html',
        title='View Check-in',
        checkin=checkin,
        project=project,
        s3_service=s3_service
    )

@checkin.route('/timeline')
@login_required
def timeline():
    # Add form creation code at beginning of the function
    form = CheckInForm()
    
    # Get all projects the user has access to through ProjectMember
    project_ids = db.session.query(ProjectMember.project_id).filter(
        ProjectMember.user_id == current_user.id
    ).all()
    project_ids = [p.project_id for p in project_ids]
    
    user_projects = Project.query.filter(Project.id.in_(project_ids)).all()
    
    # Get the selected project or default to first project
    project_id = request.args.get('project', type=int)
    if not project_id and user_projects:
        project_id = user_projects[0].id
    
    project = Project.query.get(project_id) if project_id else None
    
    # Check if already checked in today for the selected project
    today = datetime.now(pytz.UTC).date()
    already_checked_in = False
    if project and project.frequency_type == 'daily':
        already_checked_in = CheckIn.query.filter(
            CheckIn.user_id == current_user.id,
            CheckIn.project_id == project.id,
            CheckIn.check_date == today
        ).first() is not None
    
    # Get check-ins with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of check-ins per page
    
    # Get all check-ins for these projects with pagination
    checkins_pagination = CheckIn.query.filter(
        CheckIn.project_id.in_(project_ids),
        CheckIn.user_id == current_user.id
    ).order_by(
        CheckIn.check_date.desc(),
        CheckIn.check_time.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get user timezone settings
    today = datetime.now(pytz.UTC).date()
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())
    
    grouped_checkins = {
        'today': [],
        'yesterday': [],
        'this_week': [],
        'earlier': []
    }
    
    # Apply timezone conversion to all check-ins
    for checkin in checkins_pagination.items:
        # Convert check_time to local time
        checkin.check_time = to_user_timezone(checkin.check_time)
        # Add display_date attribute for template use
        checkin.display_date = to_user_timezone(
            datetime.combine(checkin.check_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
        ).date()
        
        # Use the display_date (localized date) for grouping
        if checkin.display_date == today:
            grouped_checkins['today'].append(checkin)
        elif checkin.display_date == yesterday:
            grouped_checkins['yesterday'].append(checkin)
        elif checkin.display_date >= start_of_week:
            grouped_checkins['this_week'].append(checkin)
        else:
            grouped_checkins['earlier'].append(checkin)
    
    # Create S3 service for the template
    from app.services.s3_service import S3Service
    s3_service = S3Service()
    
    return render_template(
        'checkin/timeline.html', 
        grouped_checkins=grouped_checkins, 
        projects={p.id: p for p in user_projects},
        project=project,
        pagination=checkins_pagination,
        form=form,
        already_checked_in=already_checked_in,
        s3_service=s3_service  # Add S3 service for image URLs
    )

def update_project_stats(project_id):
    """更新项目统计数据"""
    stats = ProjectStat.query.filter_by(project_id=project_id).first()
    if not stats:
        stats = ProjectStat(project_id=project_id)
        db.session.add(stats)
    
    # 计算总打卡次数
    stats.total_checkins = CheckIn.query.filter_by(project_id=project_id).count()
    
    # 计算活跃用户数（过去30天有打卡记录的用户）
    thirty_days_ago = datetime.now(pytz.UTC) - timedelta(days=30)
    active_users = db.session.query(db.func.count(db.distinct(CheckIn.user_id))).filter(
        CheckIn.project_id == project_id,
        CheckIn.check_time >= thirty_days_ago
    ).scalar()
    stats.active_users = active_users or 0
    
    # 找出最高连续打卡天数
    all_user_stats = UserProjectStat.query.filter_by(project_id=project_id).all()
    highest_streak = 0
    for user_stat in all_user_stats:
        if user_stat.highest_streak > highest_streak:
            highest_streak = user_stat.highest_streak
    
    stats.highest_streak = highest_streak
    stats.last_updated = datetime.now(pytz.UTC)
    
    return stats

def update_user_project_stats(user_id, project_id, utc_today):
    """更新用户项目统计数据
    
    Args:
        user_id: 用户ID
        project_id: 项目ID
        utc_today: UTC日期(datetime.date)
    """
    user_stats = UserProjectStat.query.filter_by(
        user_id=user_id,
        project_id=project_id
    ).first()
    
    if not user_stats:
        user_stats = UserProjectStat(user_id=user_id, project_id=project_id)
        db.session.add(user_stats)
    
    # 更新总打卡次数
    user_stats.total_checkins = CheckIn.query.filter_by(
        user_id=user_id, 
        project_id=project_id
    ).count()
    
    # 如果这是第一次打卡
    if not user_stats.last_checkin_date:
        user_stats.current_streak = 1
        user_stats.highest_streak = 1
        user_stats.last_checkin_date = utc_today
        return user_stats
    
    # 计算连续打卡天数 - 使用UTC日期进行比较
    if user_stats.last_checkin_date == utc_today - timedelta(days=1):
        # 连续打卡
        user_stats.current_streak += 1
        if user_stats.current_streak > user_stats.highest_streak:
            user_stats.highest_streak = user_stats.current_streak
    elif user_stats.last_checkin_date == utc_today:
        # 今天已经打卡过了，不更新streak
        pass
    else:
        # 断了连续性
        user_stats.current_streak = 1
    
    user_stats.last_checkin_date = utc_today
    return user_stats

def can_view_checkin(viewer_id, owner_id, project_id):
    """Determine if a user can view another user's check-ins
    
    Visibility criteria:
    1. Users can always see their own check-ins
    2. Both users must be members of the project
    3. Both users must be friends
    
    Args:
        viewer_id: The user trying to view the check-in
        owner_id: The user who created the check-in
        project_id: The project ID
        
    Returns:
        bool: True if viewer can see owner's check-ins
    """
    # Users can always see their own check-ins
    if viewer_id == owner_id:
        return True
    
    # Check if both users are members of the project
    from app.models.models import ProjectMember
    
    viewer_is_member = ProjectMember.query.filter_by(
        user_id=viewer_id, project_id=project_id
    ).first() is not None
    
    owner_is_member = ProjectMember.query.filter_by(
        user_id=owner_id, project_id=project_id
    ).first() is not None
    
    if not (viewer_is_member and owner_is_member):
        return False
    
    # Check if users are friends
    from app.models.models import FriendRelationship
    are_friends = FriendRelationship.are_friends(viewer_id, owner_id)
    
    return are_friends

@checkin.route('/api/project/<int:project_id>', methods=['GET'])
@login_required
def get_project_details(project_id):
    # Check if user has access to this project
    is_member = ProjectMember.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first() is not None
    
    if not is_member:
        return jsonify({
            'success': False,
            'message': 'Project not found or you don\'t have access'
        }), 404
    
    project = Project.query.get_or_404(project_id)
    
    return jsonify({
        'success': True,
        'project': {
            'id': project.id,
            'name': project.name,
            'icon': project.icon,
            'color': project.color
        }
    })

@checkin.route('/api/checkin', methods=['POST'])
@login_required
def ajax_checkin():
    """
    API endpoint for creating a check-in with optional image uploads
    
    Accepts form data with:
    - project_id: ID of the project
    - note: Text content for the check-in
    - images: Optional file uploads (multiple)
    """
    # Accept both JSON and form data requests
    if request.is_json:
        data = request.json
        project_id = data.get('project_id')
        note = data.get('note', '')
        has_images = False
    else:
        project_id = request.form.get('project_id')
        note = request.form.get('note', '')
        has_images = bool(request.files) and any(request.files.getlist('images'))
    
    if not project_id:
        return jsonify({
            'success': False,
            'message': 'Project ID is required'
        }), 400
    
    # Validate project access
    project = Project.query.get_or_404(project_id)
    is_member = ProjectMember.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first() is not None
    
    if not is_member:
        return jsonify({
            'success': False,
            'message': 'You don\'t have access to this project'
        }), 403
    
    # Get current time in UTC and user's local timezone
    now_utc = datetime.now(pytz.UTC)
    local_now = to_user_timezone(now_utc)
    user_today = local_now.date()

    # Check for existing check-in today
    start_of_day_local = datetime.combine(user_today, datetime.min.time())
    end_of_day_local = datetime.combine(user_today, datetime.max.time())

    user_tz = get_user_timezone()
    start_of_day_utc = user_tz.localize(start_of_day_local).astimezone(pytz.UTC)
    end_of_day_utc = user_tz.localize(end_of_day_local).astimezone(pytz.UTC)

    today_checkin = CheckIn.query.filter(
        CheckIn.user_id == current_user.id,
        CheckIn.project_id == project.id,
        CheckIn.check_time >= start_of_day_utc,
        CheckIn.check_time <= end_of_day_utc
    ).first()
    
    if project.frequency_type == 'daily' and today_checkin:
        return jsonify({
            'success': False,
            'message': 'You have already checked in today for this project'
        }), 400
    
    # Create new check-in
    checkin = CheckIn(
        user_id=current_user.id,
        project_id=project.id,
        check_date=now_utc.date(),
        check_time=now_utc,
        note=note,
        location=None
    )
    
    db.session.add(checkin)
    db.session.commit()  # Commit to get an ID for the check-in
    
    # Process images if provided
    images_added = 0
    if has_images:
        from app.utils.image_utils import process_image, create_thumbnail, is_valid_image
        from app.services.s3_service import S3Service
        
        images = request.files.getlist('images')
        if images and any(img.filename for img in images):
            s3_service = S3Service()
            max_image_size = current_app.config.get('MAX_IMAGE_SIZE', 5 * 1024 * 1024)
            allowed_extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', 
                                                   ['jpg', 'jpeg', 'png', 'gif', 'webp'])
            
            for image in images:
                if image and image.filename:
                    # Check file size
                    image_data = image.read()
                    if len(image_data) > max_image_size:
                        current_app.logger.warning(f"Image {image.filename} exceeds maximum size")
                        continue
                    
                    # Validate image type
                    if not is_valid_image(image_data, allowed_extensions):
                        current_app.logger.warning(f"File {image.filename} is not a valid image or has unsupported format")
                        continue
                    
                    try:
                        # Process the image (resize, optimize)
                        processed_data, content_type, width, height = process_image(image_data)
                        
                        if processed_data and content_type:
                            # Generate thumbnail
                            thumbnail_data = create_thumbnail(image_data)
                            
                            # Generate S3 keys
                            s3_key = s3_service.generate_s3_key(current_user.id, project.id, image.filename)
                            thumbnail_key = f"thumbnails/{s3_key}"
                            
                            # Upload to S3
                            s3_service.upload_file(processed_data, s3_key, content_type)
                            if thumbnail_data:
                                s3_service.upload_file(thumbnail_data, thumbnail_key, 'image/jpeg')
                            
                            # Add image to check-in
                            checkin.add_image(
                                s3_key=s3_key,
                                original_filename=image.filename,
                                content_type=content_type,
                                file_size=len(processed_data),
                                is_public=False  # Default to private
                            )
                            
                            images_added += 1
                            current_app.logger.info(f"Successfully added image {image.filename} to check-in {checkin.id}")
                            
                            # Limit the number of images per check-in if needed
                            if images_added >= 5:  # Limit to 5 images per check-in
                                break
                    except Exception as e:
                        current_app.logger.error(f"Failed to process image {image.filename}: {str(e)}")
                        continue
        
    # Update images count
    checkin.images_count = images_added
    
    try:
        # Notify friends
        try:
            notify_friends_of_checkin(current_user, project, checkin)
        except Exception as e:
            current_app.logger.error(f"Failed to send check-in notifications: {str(e)}")
        
        # Update project stats
        update_project_stats(project.id)
        # Update user project stats
        update_user_project_stats(current_user.id, project.id, now_utc.date())
        
        db.session.commit()
        
        response_data = {
            'success': True,
            'message': 'Check-in successful',
            'checkin_id': checkin.id,
        }
        
        if images_added > 0:
            response_data['images_added'] = images_added
            
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during check-in: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while processing your check-in'
        }), 500

@checkin.route('/api/recent-checkins/<int:project_id>', methods=['GET'])
@login_required
def get_recent_checkins(project_id):
    """API endpoint to get recent check-ins for a project"""
    # Verify user has access to this project
    is_member = ProjectMember.query.filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first() is not None
    
    if not is_member:
        return jsonify({
            'success': False,
            'message': 'Project not found or you don\'t have access'
        }), 404
    
    # Get 5 most recent check-ins for this project
    recent_checkins = CheckIn.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).order_by(CheckIn.check_time.desc()).limit(5).all()
    
    # Format the check-ins as JSON with proper timezone conversion
    checkins_json = []
    user_tz = get_user_timezone()  # Get the user's timezone
    
    for check in recent_checkins:
        # Convert UTC time to user's local timezone
        local_time = check.check_time.replace(tzinfo=pytz.UTC).astimezone(user_tz)
        formatted_time = local_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Add image information
        images_json = []
        if check.has_images():
            for image in check.images:
                # Generate the thumbnail URL through S3 service
                s3_service = S3Service()
                thumbnail_url = s3_service.get_thumbnail_url(image.s3_key)
                
                images_json.append({
                    'id': image.id,
                    's3_key': image.s3_key,
                    'thumbnail_url': thumbnail_url
                })
        
        checkins_json.append({
            'id': check.id,
            'check_time': formatted_time,
            'note': check.note,
            'has_images': check.has_images(),
            'images': images_json
        })
    
    return jsonify({
        'success': True,
        'recent_checkins': checkins_json
    })

@checkin.route('/image/<int:image_id>')
@login_required
def view_image(image_id):
    """View a specific check-in image with privacy checks"""
    image = CheckInImage.query.get_or_404(image_id)
    checkin = CheckIn.query.get(image.checkin_id)
    
    # Verify permission to view the image
    if not can_view_checkin(current_user.id, checkin.user_id, checkin.project_id) and not image.is_public:
        flash('You do not have permission to view this image.', 'danger')
        return redirect(url_for('checkin.dashboard'))
    
    # Get image URL from S3
    s3_service = S3Service()
    image_url = s3_service.generate_presigned_url(image.s3_key)
    
    if not image_url:
        flash('Failed to retrieve image.', 'danger')
        return redirect(url_for('checkin.view_checkin', checkin_id=checkin.id))
    checkin.check_time = to_user_timezone(checkin.check_time)
    return render_template(
        'checkin/view_image.html',
        title='View Image',
        image=image,
        checkin=checkin,
        image_url=image_url
    )

@checkin.route('/image/<int:image_id>/delete', methods=['POST'])
@login_required
def delete_image(image_id):
    """Delete a check-in image"""
    image = CheckInImage.query.get_or_404(image_id)
    checkin = CheckIn.query.get(image.checkin_id)
    
    # Verify ownership
    if checkin.user_id != current_user.id:
        flash('You can only delete your own images.', 'danger')
        return redirect(url_for('checkin.view_checkin', checkin_id=checkin.id))
    
    # Delete from S3
    try:
        s3_service = S3Service()
        s3_service.delete_file(image.s3_key)
        
        # Also delete thumbnail if it exists
        thumbnail_key = f"thumbnails/{image.s3_key}"
        s3_service.delete_file(thumbnail_key)
    except Exception as e:
        current_app.logger.error(f"Failed to delete image from S3: {str(e)}")
        # Continue with database deletion even if S3 deletion fails
    
    # Delete from database
    db.session.delete(image)
    db.session.commit()
    
    flash('Image deleted successfully.', 'success')
    return redirect(url_for('checkin.view_checkin', checkin_id=checkin.id))
