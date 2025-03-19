from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from app import db
from app.models.models import User, FriendRelationship
from app.friends.forms import FriendSearchForm

friends = Blueprint('friends', __name__)

@friends.route('/list')
@login_required
def list_friends():
    """Display the current user's friends list"""
    # Get accepted friend relationships where current user is the requester
    friends_as_requester = db.session.query(
        User, FriendRelationship
    ).join(
        FriendRelationship, User.id == FriendRelationship.addressee_id
    ).filter(
        FriendRelationship.requester_id == current_user.id,
        FriendRelationship.status == 'accepted'
    ).all()
    
    # Get accepted friend relationships where current user is the addressee
    friends_as_addressee = db.session.query(
        User, FriendRelationship
    ).join(
        FriendRelationship, User.id == FriendRelationship.requester_id
    ).filter(
        FriendRelationship.addressee_id == current_user.id,
        FriendRelationship.status == 'accepted'
    ).all()
    
    # Combine both query results
    friends_list = friends_as_requester + friends_as_addressee
    
    # Get pending friend requests (received by current user)
    pending_requests = db.session.query(
        User, FriendRelationship
    ).join(
        FriendRelationship, User.id == FriendRelationship.requester_id
    ).filter(
        FriendRelationship.addressee_id == current_user.id,
        FriendRelationship.status == 'pending'
    ).all()
    
    # Get sent but not yet accepted friend requests
    sent_requests = db.session.query(
        User, FriendRelationship
    ).join(
        FriendRelationship, User.id == FriendRelationship.addressee_id
    ).filter(
        FriendRelationship.requester_id == current_user.id,
        FriendRelationship.status == 'pending'
    ).all()
    
    return render_template(
        'friends/list.html',
        title='My Friends',
        friends=friends_list,
        pending_requests=pending_requests,
        sent_requests=sent_requests,
        search_form=FriendSearchForm()
    )

@friends.route('/search', methods=['GET', 'POST'])
@login_required
def search_users():
    """Search users to add as friends"""
    form = FriendSearchForm()
    users = []
    
    if form.validate_on_submit() or request.args.get('q'):
        search_term = form.search.data or request.args.get('q')
        # Search by username only (not email) for privacy reasons
        users = User.query.filter(
            User.id != current_user.id,
            User.username.like(f'%{search_term}%')
        ).all()
        
        # For each user, find relationship status with current user
        for user in users:
            relationship = FriendRelationship.get_relationship(current_user.id, user.id)
            if relationship is None:
                user.relationship_status = None  # No relationship
            else:
                user.relationship_status = relationship.status
                user.relationship = relationship  # Store the relationship object for the template
                if relationship.requester_id == current_user.id:
                    user.is_requester = True  # Current user initiated the request
                else:
                    user.is_requester = False  # Other user initiated the request
    
    return render_template(
        'friends/search.html',
        title='Find Friends',
        form=form,
        users=users,
        search_term=form.search.data or request.args.get('q', '')
    )

# The rest of the routes remain functionally the same, just update docstrings
@friends.route('/request/<int:user_id>', methods=['POST'])
@login_required
def send_request(user_id):
    """Send friend request"""
    # 检查用户是否存在
    user = User.query.get_or_404(user_id)
    
    # 检查是否已经是好友或有待处理的请求
    relationship = FriendRelationship.get_relationship(current_user.id, user.id)
    if relationship:
        if relationship.status == 'accepted':
            flash(f'你和 {user.username} 已经是好友了', 'info')
        elif relationship.status == 'pending':
            if relationship.requester_id == current_user.id:
                flash(f'你已经向 {user.username} 发送了好友请求', 'info')
            else:
                flash(f'{user.username} 已经向你发送了好友请求', 'info')
        return redirect(url_for('friends.list_friends'))
    
    # 创建新的好友请求
    new_request = FriendRelationship(
        requester_id=current_user.id,
        addressee_id=user.id
    )
    db.session.add(new_request)
    db.session.commit()
    
    flash(f'已向 {user.username} 发送好友请求', 'success')
    return redirect(url_for('friends.list_friends'))

@friends.route('/accept/<int:relationship_id>', methods=['POST'])
@login_required
def accept_request(relationship_id):
    """Accept friend request"""
    relationship = FriendRelationship.query.get_or_404(relationship_id)
    
    # 验证当前用户是请求的接收者
    if relationship.addressee_id != current_user.id:
        flash('无权处理此请求', 'danger')
        return redirect(url_for('friends.list_friends'))
    
    # 更新关系状态为已接受
    relationship.status = 'accepted'
    db.session.commit()
    
    # 获取请求者信息用于显示消息
    requester = User.query.get(relationship.requester_id)
    flash(f'你已接受 {requester.username} 的好友请求', 'success')
    return redirect(url_for('friends.list_friends'))

@friends.route('/reject/<int:relationship_id>', methods=['POST'])
@login_required
def reject_request(relationship_id):
    """Reject friend request"""
    relationship = FriendRelationship.query.get_or_404(relationship_id)
    
    # 验证当前用户是请求的接收者
    if relationship.addressee_id != current_user.id:
        flash('无权处理此请求', 'danger')
        return redirect(url_for('friends.list_friends'))
    
    # 更新关系状态为已拒绝
    relationship.status = 'rejected'
    db.session.commit()
    
    # 获取请求者信息用于显示消息
    requester = User.query.get(relationship.requester_id)
    flash(f'你已拒绝 {requester.username} 的好友请求', 'success')
    return redirect(url_for('friends.list_friends'))

@friends.route('/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_friend(user_id):
    """Remove friend"""
    relationship = FriendRelationship.get_relationship(current_user.id, user_id)
    
    if not relationship or relationship.status != 'accepted':
        flash('该用户不是你的好友', 'warning')
        return redirect(url_for('friends.list_friends'))
    
    # 获取好友信息用于显示消息
    friend = User.query.get(user_id)
    
    # 删除好友关系
    db.session.delete(relationship)
    db.session.commit()
    
    flash(f'已将 {friend.username} 从好友列表中移除', 'success')
    return redirect(url_for('friends.list_friends'))