# app/projects/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.models import Project, ProjectMember, UserProjectStat, User, ProjectInvitation, FriendRelationship, ProjectJoinRequest
from app.projects.forms import ProjectForm, ProjectInvitationForm
from datetime import datetime

projects = Blueprint('projects', __name__)

@projects.route('/list')
@login_required
def list_projects():
    # Get all user projects in a single query (both created and joined)
    user_projects = db.session.query(Project, ProjectMember).join(
        ProjectMember, Project.id == ProjectMember.project_id
    ).filter(
        ProjectMember.user_id == current_user.id
    ).all()
    
    # Split projects into created and joined in Python
    created_projects = []
    joined_projects = []
    
    for project, member in user_projects:
        if project.creator_id == current_user.id:
            created_projects.append((project, member))
        else:
            joined_projects.append((project, member))
    
    # 获取可通过邀请加入的项目（排除用户已加入的项目）以及创建者信息
    invitation_projects = db.session.query(Project, User).join(
        User, Project.creator_id == User.id
    ).filter(
        Project.visibility == 'invitation',
        ~Project.id.in_(
            db.session.query(ProjectMember.project_id).filter(
                ProjectMember.user_id == current_user.id
            )
        )
    ).all()
    
    return render_template(
        'projects/list.html',
        title='My Projects',
        created_projects=created_projects,
        joined_projects=joined_projects,
        invitation_projects=invitation_projects
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
            frequency_type=form.frequency_type.data,
            visibility=form.visibility.data,
            icon=form.icon.data,
            color=form.color.data
        )
        db.session.add(project)
        db.session.commit()
        
        # 创建者自动成为项目成员
        member = ProjectMember(
            user_id=current_user.id,
            project_id=project.id,
            role='creator'
        )
        db.session.add(member)
        
        # 初始化项目统计
        from app.models.models import ProjectStat
        stats = ProjectStat(project_id=project.id)
        db.session.add(stats)
        
        # 初始化用户项目统计
        user_stats = UserProjectStat(
            user_id=current_user.id,
            project_id=project.id
        )
        db.session.add(user_stats)
        
        db.session.commit()
        
        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    
    return render_template('projects/create.html', title='创建项目', form=form)

@projects.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 检查是否为创建者
    if project.creator_id != current_user.id:
        flash('Only the project creator can edit this project', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    form = ProjectForm()
    if form.validate_on_submit():
        project.name = form.name.data
        project.description = form.description.data
        project.frequency_type = form.frequency_type.data
        project.visibility = form.visibility.data
        project.icon = form.icon.data
        project.color = form.color.data
        db.session.commit()
        
        flash(f'Project "{project.name}" has been updated', 'success')
        return redirect(url_for('projects.view_project', project_id=project.id))
    elif request.method == 'GET':
        form.name.data = project.name
        form.description.data = project.description
        form.frequency_type.data = project.frequency_type
        form.visibility.data = project.visibility
        form.icon.data = project.icon
        form.color.data = project.color
    
    return render_template('projects/edit.html', title='编辑项目', form=form, project=project)

@projects.route('/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 检查用户是否有权限查看此项目
    member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()
    
    # 私有项目只有成员可以查看
    if not (member or project.visibility == 'invitation'):
        flash('你没有权限查看此项目', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    # 获取项目统计
    from app.models.models import ProjectStat
    stats = ProjectStat.query.filter_by(project_id=project_id).first()
    
    # 获取用户项目统计
    user_stats = None
    if member:
        user_stats = UserProjectStat.query.filter_by(
            user_id=current_user.id,
            project_id=project_id
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
    
    # Check if user is already a member
    existing_member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()
    
    if existing_member:
        flash('You are already a member of this project.', 'info')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # If the project is private, prevent direct joining
    if project.visibility == 'private':
        flash('This project is private. You cannot join it directly.', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    # For invitation-based projects, create a join request instead of direct joining
    if project.visibility == 'invitation':
        # Check if there's already a pending request
        from app.models.models import ProjectJoinRequest
        existing_request = ProjectJoinRequest.query.filter_by(
            project_id=project_id,
            user_id=current_user.id,
            status='pending'
        ).first()
        
        if existing_request:
            flash('You already have a pending join request for this project.', 'info')
            return redirect(url_for('projects.view_project', project_id=project_id))
        
        # Create new join request
        join_request = ProjectJoinRequest(
            project_id=project_id,
            user_id=current_user.id,
            message=request.form.get('message', '') # 可选消息字段
        )
        db.session.add(join_request)
        db.session.commit()
        
        flash('Your request to join this project has been submitted and is awaiting approval.', 'success')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    flash('Cannot join this project under current settings.', 'danger')
    return redirect(url_for('projects.list_projects'))

@projects.route('/<int:project_id>/leave', methods=['POST'])
@login_required
def leave_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 检查是否为项目创建者
    if project.creator_id == current_user.id:
        flash('项目创建者不能离开项目。如需删除项目，请使用删除功能。', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # 检查是否为项目成员
    member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()
    
    if not member:
        flash('你不是此项目的成员', 'info')
        return redirect(url_for('projects.list_projects'))
    
    # 删除成员记录
    db.session.delete(member)
    db.session.commit()
    
    flash(f'你已离开项目 "{project.name}"', 'success')
    return redirect(url_for('projects.list_projects'))

@projects.route('/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 检查是否为创建者
    if project.creator_id != current_user.id:
        flash('只有项目创建者可以删除项目', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # 删除项目
    db.session.delete(project)
    db.session.commit()
    
    flash(f'项目 "{project.name}" 已被删除', 'success')
    return redirect(url_for('projects.list_projects'))

@projects.route('/<int:project_id>/members')
@login_required
def members(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check if the current user is project creator or member
    is_creator = project.creator_id == current_user.id
    is_member = ProjectMember.query.filter_by(
        project_id=project_id, 
        user_id=current_user.id
    ).first() is not None
    
    if not (is_creator or is_member):
        flash('You do not have access to this project', 'danger')
        return redirect(url_for('projects.list_projects'))
    
    # Get project members
    members = db.session.query(
        User, ProjectMember
    ).join(
        ProjectMember, User.id == ProjectMember.user_id
    ).filter(
        ProjectMember.project_id == project_id
    ).all()
    
    # Get pending invitations
    pending_invitations = db.session.query(
        User, ProjectInvitation
    ).join(
        ProjectInvitation, User.id == ProjectInvitation.invitee_id
    ).filter(
        ProjectInvitation.project_id == project_id,
        ProjectInvitation.status == 'pending'
    ).all()
    
    # Create invitation form
    invitation_form = None
    if is_creator:
        invitation_form = ProjectInvitationForm(user_id=current_user.id)
        
        # Exclude users who are already members or have pending invitations
        existing_member_ids = [member[0].id for member in members]
        pending_invitee_ids = [invitation[0].id for invitation in pending_invitations]
        excluded_ids = existing_member_ids + pending_invitee_ids
        
        # Filter options
        if invitation_form.friend_id.choices:
            invitation_form.friend_id.choices = [
                (id, label) for id, label in invitation_form.friend_id.choices 
                if id not in excluded_ids
            ]
    
    return render_template(
        'projects/members.html',
        title=f'{project.name} - Members',
        project=project,
        members=members,
        pending_invitations=pending_invitations,
        invitation_form=invitation_form,
        is_creator=is_creator
    )

@projects.route('/<int:project_id>/invite', methods=['POST'])
@login_required
def invite_member(project_id):
    """Invite a friend to join the project"""
    project = Project.query.get_or_404(project_id)
    
    # Check if current user is project creator
    if project.creator_id != current_user.id:
        flash('Only the project creator can invite members', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))
    
    # Check if project is private - reject invitations
    if project.visibility == 'private':
        flash('You cannot invite members to a private project. Change project visibility to "By Invitation" first.', 'warning')
        return redirect(url_for('projects.members', project_id=project_id))
    
    # Validate form
    form = ProjectInvitationForm(user_id=current_user.id)
    if form.validate_on_submit():
        friend_id = form.friend_id.data
        
        # Check if already a member
        is_member = ProjectMember.query.filter_by(
            project_id=project_id, 
            user_id=friend_id
        ).first() is not None
        
        if is_member:
            flash('This user is already a project member', 'warning')
            return redirect(url_for('projects.members', project_id=project_id))
        
        # Check if already invited
        existing_invitation = ProjectInvitation.query.filter_by(
            project_id=project_id,
            invitee_id=friend_id,
            status='pending'
        ).first()
        
        if existing_invitation:
            flash('An invitation has already been sent to this user', 'info')
            return redirect(url_for('projects.members', project_id=project_id))
        
        # Create new invitation
        invitation = ProjectInvitation(
            project_id=project_id,
            inviter_id=current_user.id,
            invitee_id=friend_id
        )
        db.session.add(invitation)
        db.session.commit()
        
        # Get invitee info
        invitee = User.query.get(friend_id)
        flash(f'Invitation sent to {invitee.username}', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('projects.members', project_id=project_id))

@projects.route('/invitations')
@login_required
def my_invitations():
    """Display all project invitations for the current user"""
    # Get all pending invitations for current user
    invitations = db.session.query(
        Project, User, ProjectInvitation
    ).join(
        ProjectInvitation, Project.id == ProjectInvitation.project_id
    ).join(
        User, User.id == ProjectInvitation.inviter_id
    ).filter(
        ProjectInvitation.invitee_id == current_user.id,
        ProjectInvitation.status == 'pending'
    ).all()
    
    return render_template(
        'projects/invitations.html',
        title='My Project Invitations',
        invitations=invitations
    )

@projects.route('/invitations/<int:invitation_id>/accept', methods=['POST'])
@login_required
def accept_invitation(invitation_id):
    """Accept a project invitation"""
    invitation = ProjectInvitation.query.get_or_404(invitation_id)
    
    # Check if current user is the invitee
    if invitation.invitee_id != current_user.id:
        flash('You cannot process this invitation', 'danger')
        return redirect(url_for('projects.my_invitations'))
    
    # Check if invitation status is pending
    if invitation.status != 'pending':
        flash('This invitation has already been processed', 'warning')
        return redirect(url_for('projects.my_invitations'))
    
    # Get project info
    project = Project.query.get(invitation.project_id)
    
    # Update invitation status to accepted
    invitation.status = 'accepted'
    
    # Add user as project member
    member = ProjectMember(user_id=current_user.id, project_id=invitation.project_id)
    db.session.add(member)
    db.session.commit()
    
    flash(f'You have joined the project: {project.name}', 'success')
    return redirect(url_for('projects.view_project', project_id=invitation.project_id))

@projects.route('/invitations/<int:invitation_id>/reject', methods=['POST'])
@login_required
def reject_invitation(invitation_id):
    """Reject a project invitation"""
    invitation = ProjectInvitation.query.get_or_404(invitation_id)
    
    # Check if current user is the invitee
    if invitation.invitee_id != current_user.id:
        flash('You cannot process this invitation', 'danger')
        return redirect(url_for('projects.my_invitations'))
    
    # Check if invitation status is pending
    if invitation.status != 'pending':
        flash('This invitation has already been processed', 'warning')
        return redirect(url_for('projects.my_invitations'))
    
    # Get project info
    project = Project.query.get(invitation.project_id)
    
    # Update invitation status to rejected
    invitation.status = 'rejected'
    db.session.commit()
    
    flash(f'You have declined to join the project: {project.name}', 'info')
    return redirect(url_for('projects.my_invitations'))

@projects.route('/<int:project_id>/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_member(project_id, user_id):
    """Remove a member from the project"""
    project = Project.query.get_or_404(project_id)
    
    # Check if current user is project creator
    if project.creator_id != current_user.id:
        flash('Only the project creator can remove members', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))
    
    # Check if attempting to remove the creator (not allowed)
    if user_id == project.creator_id:
        flash('Cannot remove the project creator', 'danger')
        return redirect(url_for('projects.members', project_id=project_id))
    
    # Get member info
    member_record = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=user_id
    ).first()
    
    if not member_record:
        flash('This user is not a project member', 'warning')
        return redirect(url_for('projects.members', project_id=project_id))
    
    # Get user info for display message
    user = User.query.get(user_id)
    
    # Remove member
    db.session.delete(member_record)
    db.session.commit()
    
    flash(f'Removed {user.username} from the project', 'success')
    return redirect(url_for('projects.members', project_id=project_id))

@projects.route('/<int:project_id>/join_requests')
@login_required
def join_requests(project_id):
    """Show project join requests"""
    project = Project.query.get_or_404(project_id)
    
    # Check if current user is project creator
    if project.creator_id != current_user.id:
        flash('Only the project creator can manage join requests', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Get all pending join requests
    pending_requests = db.session.query(
        User, ProjectJoinRequest
    ).join(
        ProjectJoinRequest, User.id == ProjectJoinRequest.user_id
    ).filter(
        ProjectJoinRequest.project_id == project_id,
        ProjectJoinRequest.status == 'pending'
    ).all()
    
    return render_template(
        'projects/join_requests.html',
        title=f'{project.name} - Join Requests',
        project=project,
        pending_requests=pending_requests
    )

@projects.route('/<int:project_id>/join_requests/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_join_request(project_id, request_id):
    """Approve a project join request"""
    project = Project.query.get_or_404(project_id)
    join_request = ProjectJoinRequest.query.get_or_404(request_id)
    
    # Check if current user is project creator
    if project.creator_id != current_user.id:
        flash('Only the project creator can manage join requests', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Verify request belongs to this project
    if join_request.project_id != project_id:
        flash('Request ID mismatch', 'danger')
        return redirect(url_for('projects.join_requests', project_id=project_id))
    
    # Get user info
    user = User.query.get(join_request.user_id)
    if not user:
        flash('User not found', 'warning')
        return redirect(url_for('projects.join_requests', project_id=project_id))
    
    # Check if already a member
    existing_member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=user.id
    ).first()
    
    if existing_member:
        # Update request status to approved
        join_request.status = 'approved'
        db.session.commit()
        flash(f'{user.username} is already a project member', 'info')
        return redirect(url_for('projects.join_requests', project_id=project_id))
    
    # Add user as project member
    member = ProjectMember(
        project_id=project_id,
        user_id=user.id,
        role='member'
    )
    db.session.add(member)
    
    # Update request status
    join_request.status = 'approved'
    db.session.commit()
    
    flash(f'Approved {user.username} to join the project', 'success')
    return redirect(url_for('projects.join_requests', project_id=project_id))

@projects.route('/<int:project_id>/join_requests/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_join_request(project_id, request_id):
    """Reject a project join request"""
    project = Project.query.get_or_404(project_id)
    join_request = ProjectJoinRequest.query.get_or_404(request_id)
    
    # Check if current user is project creator
    if project.creator_id != current_user.id:
        flash('Only the project creator can manage join requests', 'danger')
        return redirect(url_for('projects.view_project', project_id=project_id))
    
    # Verify request belongs to this project
    if join_request.project_id != project_id:
        flash('Request ID mismatch', 'danger')
        return redirect(url_for('projects.join_requests', project_id=project_id))
    
    # Get user info
    user = User.query.get(join_request.user_id)
    username = user.username if user else "Unknown user"
    
    # Update request status
    join_request.status = 'rejected'
    db.session.commit()
    
    flash(f'Rejected {username}\'s join request', 'info')
    return redirect(url_for('projects.join_requests', project_id=project_id))