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

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, nullable=False)  # 创建者ID
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    frequency_type = db.Column(db.String(20), nullable=False, default='daily')  # 'daily'(每日一次) 或 'unlimited'(不限次数)
    is_public = db.Column(db.Boolean, default=False)  # 是否公开
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
