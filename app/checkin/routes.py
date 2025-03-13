# app/checkin/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta  # 添加 timedelta 导入
from app import db
from app.models.models import CheckIn, Project, ProjectMember, ProjectStat, UserProjectStat, User  # 添加 User
from app.checkin.forms import CheckInForm, ProjectSelectForm
from app.utils.timezone import get_user_timezone, to_user_timezone
import pytz

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
    
    # 默认选择第一个项目，或者从URL参数获取
    project_id = request.args.get('project', type=int)
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
    
    # Get current time in UTC
    now_utc = datetime.now(pytz.UTC)
    # Convert to user's timezone for display purposes
    local_now = to_user_timezone(now_utc)
    
    # Check if user already checked in today for this project - using UTC date
    today_checkin = CheckIn.query.filter_by(
        user_id=current_user.id,
        project_id=project.id,
        check_date=now_utc.date()  # Use UTC date for database query
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
    
    return render_template(
        'checkin/dashboard.html',
        title='Dashboard',
        form=form,
        project_select_form=project_select_form,
        already_checked_in=bool(today_checkin) if project.frequency_type == 'daily' else False,
        recent_checkins=recent_checkins,
        project=project,
        projects=projects,
        user_stats=user_stats
    )

@checkin.route('/history')
@login_required
def history():
    # 获取用户可参与的项目
    projects = db.session.query(Project).join(
        ProjectMember, Project.id == ProjectMember.project_id
    ).filter(
        ProjectMember.user_id == current_user.id
    ).all()
    
    # 从URL参数获取项目ID和页码
    project_id = request.args.get('project', type=int)
    page = request.args.get('page', 1, type=int)
    
    # 获取项目
    if project_id is None and projects:
        project_id = projects[0].id
    
    project = next((p for p in projects if p.id == project_id), None) if project_id else None
    
    if not project:
        flash('Project not found or you don\'t have access.', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    # 从URL获取视图模式，如果没有提供，则根据项目可见性设置默认值
    view_mode = request.args.get('view')
    if view_mode is None:
        # 公开项目默认展示所有人的记录，私有项目默认只展示个人记录
        view_mode = 'all' if project.is_public else 'personal'
    
    # 准备项目选择表单
    project_select_form = ProjectSelectForm()
    project_select_form.project.choices = [(p.id, p.name) for p in projects]
    if project_id:
        project_select_form.project.default = project_id
        project_select_form.process()
    
    # 查询打卡记录，根据视图模式决定是查看个人还是所有成员的记录
    if view_mode == 'all' and project.is_public:
        # 公开项目 - 查看所有成员的打卡记录
        checkins_query = db.session.query(
            CheckIn, User.username
        ).join(
            User, CheckIn.user_id == User.id
        ).filter(
            CheckIn.project_id == project.id
        ).order_by(
            CheckIn.check_date.desc(), 
            CheckIn.check_time.desc()
        )
    else:
        # 私有项目或个人视图 - 只查看自己的打卡记录
        checkins_query = db.session.query(
            CheckIn, db.literal(current_user.username).label('username')
        ).filter(
            CheckIn.user_id == current_user.id,
            CheckIn.project_id == project.id
        ).order_by(
            CheckIn.check_date.desc(), 
            CheckIn.check_time.desc()
        )
    
    # 分页
    page_items = checkins_query.paginate(page=page, per_page=10)
    
    # Convert UTC times to user's local timezone
    for item in page_items.items:
        # Each item is a tuple of (CheckIn, username)
        checkin = item[0]
        # Convert check_time to local time
        checkin.check_time = to_user_timezone(checkin.check_time)
        # Add display_date attribute for template use
        checkin.display_date = to_user_timezone(
            datetime.combine(checkin.check_date, datetime.min.time()).replace(tzinfo=pytz.UTC)
        ).date()
    
    return render_template(
        'checkin/history.html',
        title='Check-in History',
        project=project,
        checkins=page_items,
        project_select_form=project_select_form,
        view_mode=view_mode,
        is_public=project.is_public
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
