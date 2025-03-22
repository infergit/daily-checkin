# app/models/models.py
from datetime import datetime, timezone
import pytz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    date_registered = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # 移除关系定义，改为通过业务代码维护关系
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def get_pending_invitations_count(self):
        """Get the number of pending project invitations for this user"""
        from app.models.models import ProjectInvitation
        return ProjectInvitation.query.filter_by(
            invitee_id=self.id, 
            status='pending'
        ).count()

    def get_preference(self, key, default=None):
        """Get a user preference by key"""
        pref = UserPreference.query.filter_by(user_id=self.id, key=key).first()
        return pref.value if pref else default

    def set_preference(self, key, value):
        """Set a user preference"""
        pref = UserPreference.query.filter_by(user_id=self.id, key=key).first()
        if pref:
            pref.value = str(value)
        else:
            pref = UserPreference(user_id=self.id, key=key, value=str(value))
            db.session.add(pref)
        db.session.commit()

    def wants_checkin_notifications(self):
        """Check if user wants to receive check-in notifications"""
        return self.get_preference('receive_checkin_notifications', 'N') == 'Y'

    def has_valid_telegram(self):
        """Check if user has a valid Telegram chat ID configured"""
        return bool(self.get_preference('telegram_chat_id', None))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, nullable=False)  # 创建者ID
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    frequency_type = db.Column(db.String(20), nullable=False, default='daily')  # 'daily'(每日一次) 或 'unlimited'(不限次数)
    # 替换 is_public 字段
    visibility = db.Column(db.String(20), default='private')  # 'private'(仅自己可见), 'invitation'(需要邀请才能加入)
    icon = db.Column(db.String(50), nullable=True)  # 可选图标
    color = db.Column(db.String(20), nullable=True)  # 可选颜色
    
    def __repr__(self):
        return f'<Project {self.name}>'

class ProjectMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), default='member')  # 'creator', 'admin', 'member'
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 确保一个用户在一个项目中只有一个角色
    __table_args__ = (
        db.UniqueConstraint('project_id', 'user_id', name='unique_project_member'),
    )
    
    def __repr__(self):
        return f'<ProjectMember project_id={self.project_id} user_id={self.user_id}>'

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # 移除外键约束
    project_id = db.Column(db.Integer, nullable=False)  # 新增：关联到项目
    check_date = db.Column(db.Date, nullable=False)  # Store UTC date
    check_time = db.Column(db.DateTime, nullable=False)  # Store UTC time
    note = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(200), nullable=True)  # 可选：位置信息
    
    def __repr__(self):
        return f'<CheckIn user_id={self.user_id} project_id={self.project_id} on {self.check_date}>'

class ProjectStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False, unique=True)
    total_checkins = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    highest_streak = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<ProjectStat project_id={self.project_id}>'

class UserProjectStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    project_id = db.Column(db.Integer, nullable=False)
    total_checkins = db.Column(db.Integer, default=0)
    current_streak = db.Column(db.Integer, default=0)
    highest_streak = db.Column(db.Integer, default=0)
    last_checkin_date = db.Column(db.Date, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'project_id', name='unique_user_project_stat'),
    )
    
    def __repr__(self):
        return f'<UserProjectStat user_id={self.user_id} project_id={self.project_id}>'

class FriendRelationship(db.Model):
    """用户好友关系模型
    
    用于存储用户间的好友关系，包括请求状态。
    状态包括：pending (待接受)、accepted (已接受)、rejected (已拒绝)
    """
    __tablename__ = 'friend_relationships'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, nullable=False)  # 发起好友请求的用户ID
    addressee_id = db.Column(db.Integer, nullable=False)  # 接收好友请求的用户ID
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('requester_id', 'addressee_id', name='uq_friend_relationship'),
    )
    
    def __repr__(self):
        return f'<FriendRelationship {self.requester_id}-{self.addressee_id}: {self.status}>'
    
    @staticmethod
    def get_relationship(user_id1, user_id2):
        """获取两个用户间的好友关系
        
        返回None表示没有关系记录
        """
        return FriendRelationship.query.filter(
            ((FriendRelationship.requester_id == user_id1) & 
             (FriendRelationship.addressee_id == user_id2)) |
            ((FriendRelationship.requester_id == user_id2) & 
             (FriendRelationship.addressee_id == user_id1))
        ).first()
    
    @staticmethod
    def are_friends(user_id1, user_id2):
        """检查两个用户是否为好友（双向接受的关系）"""
        relationship = FriendRelationship.get_relationship(user_id1, user_id2)
        return relationship is not None and relationship.status == 'accepted'

class ProjectInvitation(db.Model):
    """项目邀请模型
    
    用于存储项目邀请记录，包括邀请状态。
    状态包括：pending (待接受)、accepted (已接受)、rejected (已拒绝)
    """
    __tablename__ = 'project_invitations'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)  # 被邀请的项目ID
    inviter_id = db.Column(db.Integer, nullable=False)  # 邀请人ID
    invitee_id = db.Column(db.Integer, nullable=False)  # 被邀请人ID
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('project_id', 'invitee_id', name='uq_project_invitation'),
    )
    
    def __repr__(self):
        return f'<ProjectInvitation project_id={self.project_id} invitee_id={self.invitee_id} status={self.status}>'
    
    @staticmethod
    def get_pending_invitation(project_id, invitee_id):
        """获取待处理的项目邀请"""
        return ProjectInvitation.query.filter_by(
            project_id=project_id, 
            invitee_id=invitee_id,
            status='pending'
        ).first()
        
    @staticmethod
    def has_pending_invitation(project_id, invitee_id):
        """检查是否有待处理的项目邀请"""
        return ProjectInvitation.get_pending_invitation(project_id, invitee_id) is not None
        
    @staticmethod
    def get_user_pending_invitations(user_id):
        """获取用户所有待处理的项目邀请"""
        return ProjectInvitation.query.filter_by(
            invitee_id=user_id, 
            status='pending'
        ).all()

class ProjectJoinRequest(db.Model):
    """项目加入请求模型
    
    用于存储用户发起的加入项目请求，需要创建者审批。
    状态包括：pending (待审批)、accepted (已接受)、rejected (已拒绝)
    """
    __tablename__ = 'project_join_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)  # 请求加入的项目ID
    user_id = db.Column(db.Integer, nullable=False)     # 申请人ID
    message = db.Column(db.Text, nullable=True)         # 申请信息(可选)
    status = db.Column(db.String(20), default='pending') # 'pending', 'accepted', 'rejected'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('project_id', 'user_id', name='uq_project_join_request'),
    )
    
    def __repr__(self):
        return f'<ProjectJoinRequest project_id={self.project_id} user_id={self.user_id} status={self.status}>'

class UserPreference(db.Model):
    """Model for storing user preferences as key-value pairs"""
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # No foreign key constraint
    key = db.Column(db.String(64), nullable=False)   # Preference name
    value = db.Column(db.String(255))                # Preference value as string
    
    # Ensure each user has only one entry per preference key
    __table_args__ = (db.UniqueConstraint('user_id', 'key'),)
    
    def __repr__(self):
        return f'<UserPreference id={self.id} user_id={self.user_id} key={self.key}>'
