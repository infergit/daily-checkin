# app/projects/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.models import Project, ProjectMember, UserProjectStat
from app.projects.forms import ProjectForm, ProjectInviteForm
from datetime import datetime

projects = Blueprint('projects', __name__)

@projects.route('/list')
@login_required
def list_projects():
    # 获取用户所属的项目
    user_projects = db.session.query(Project, ProjectMember).join(
        ProjectMember, Project.id == ProjectMember.project_id
    ).filter(
        ProjectMember.user_id == current_user.id
    ).all()
    
    # 获取公开项目
    public_projects = Project.query.filter_by(is_public=True).all()
    
    return render_template(
        'projects/list.html',
        title='My Projects',
        user_projects=user_projects,
        public_projects=public_projects
    )

@projects.route('/create', methods=['GET', 'POST'])
@login_required
def create_project():
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            name=form.name.data,
            description=form.description.data,
            creator_id=current_user.id,
            is_public=form.is_public.data,
            frequency_type=form.frequency_type.data,
            icon=form.icon.data,
            color=form.color.data
        )
        db.session.add(project)
        db.session.commit()
        
        # 创建者加入项目作为管理员
        member = ProjectMember(
            project_id=project.id,
            user_id=current_user.id,
            role='creator'
        )
        db.session.add(member)
        
        # 初始化项目统计
        from app.models.models import ProjectStat
        stats = ProjectStat(project_id=project.id)
        db.session.add(stats)
        
        # 初始化创建者的项目统计
        user_stats = UserProjectStat(
            user_id=current_user.id,
            project_id=project.id
        )
        db.session.add(user_stats)
        
        db.session.commit()
        
        flash('Project created successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    return render_template('projects/create.html', title='Create Project', form=form)

@projects.route('/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 检查用户是否有权访问该项目
    member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()
    
    if not (member or project.is_public):
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    # 获取项目统计信息
    from app.models.models import ProjectStat
    stats = ProjectStat.query.filter_by(project_id=project_id).first()
    
    # 获取用户在该项目的统计信息
    user_stats = None
    if member:
        user_stats = UserProjectStat.query.filter_by(
            project_id=project_id,
            user_id=current_user.id
        ).first()
    
    return render_template(
        'projects/view.html',
        title=project.name,
        project=project,
        member=member,
        stats=stats,
        user_stats=user_stats
    )

@projects.route('/<int:project_id>/join', methods=['POST'])
@login_required
def join_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check if the project is public or if the user already has access
    existing_member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()
    
    if existing_member:
        flash('You are already a member of this project.', 'info')
    elif not project.is_public:
        flash('This project is private. You cannot join it directly.', 'danger')
    else:
        # Add user as a member
        member = ProjectMember(
            project_id=project_id,
            user_id=current_user.id,
            role='member'
        )
        db.session.add(member)
        
        # Initialize user project statistics
        user_stats = UserProjectStat(
            user_id=current_user.id,
            project_id=project_id
        )
        db.session.add(user_stats)
        db.session.commit()
        
        flash('You have successfully joined the project!', 'success')
    
    return redirect(url_for('projects.view_project', project_id=project_id))