from app import create_app, db
from app.models.models import User, CheckIn, Project, ProjectMember, UserProjectStat, ProjectStat
from datetime import datetime, timezone

def migrate_data():
    app = create_app()
    with app.app_context():
        # 1. 创建默认项目
        default_project = Project(
            name="默认打卡项目",
            description="包含系统迁移前的所有打卡记录",
            creator_id=1,  # 假设ID为1的用户是管理员，根据实际情况调整
            frequency_type="daily",
            is_public=False,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(default_project)
        db.session.flush()  # 获取项目ID
        
        print(f"创建默认项目，ID: {default_project.id}")
        
        # 2. 将所有用户添加为项目成员
        users = User.query.all()
        for user in users:
            member = ProjectMember(
                user_id=user.id,
                project_id=default_project.id,
                role='member' if user.id != 1 else 'creator',
                joined_at=datetime.now(timezone.utc)
            )
            db.session.add(member)
            print(f"添加用户 {user.username} 到默认项目")
        
        # 3. 更新所有现有签到记录
        checkins = CheckIn.query.all()
        print(f"更新 {len(checkins)} 条现有打卡记录")
        
        for checkin in checkins:
            checkin.project_id = default_project.id
        
        # 4. 创建项目统计
        stats = ProjectStat(project_id=default_project.id)
        db.session.add(stats)
        
        # 5. 为每个用户创建项目统计
        for user in users:
            # 计算用户的打卡次数
            user_checkins = CheckIn.query.filter_by(user_id=user.id).all()
            
            user_stats = UserProjectStat(
                user_id=user.id,
                project_id=default_project.id,
                total_checkins=len(user_checkins)
            )
            db.session.add(user_stats)
            print(f"为用户 {user.username} 创建项目统计")
        
        # 提交所有更改
        db.session.commit()
        print("数据迁移完成!")

if __name__ == "__main__":
    migrate_data()