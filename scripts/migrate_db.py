#!/usr/bin/env python
# scripts/migrate_db.py
import os
import sys
import sqlite3
import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, create_app

def migrate_database():
    """
    Migrate the database schema:
    1. Convert Project.is_public boolean to Project.visibility string
    2. Add new tables:
       - friend_relationships (Friend system)
       - project_invitations (Project invitation system)
       - project_join_requests (Join request workflow)
    """
    app = create_app()
    
    # 使用Flask的instance_path和数据库URI获取正确路径
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"Database URI from config: {db_uri}")
    
    # 从URI中提取文件名
    if db_uri.startswith('sqlite:///'):
        db_filename = db_uri.replace('sqlite:///', '')
        
        # 处理相对路径 - 这是关键改进
        if not os.path.isabs(db_filename):
            # 使用Flask的instance_path确保与应用程序使用相同的路径
            db_path = os.path.join(app.instance_path, os.path.basename(db_filename))
            print(f"Using Flask instance path: {app.instance_path}")
        else:
            db_path = db_filename
    else:
        print(f"Unsupported database URI: {db_uri}")
        return False
    
    print(f"Resolved database path: {db_path}")
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        # 尝试几个常见位置
        alternate_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'app.db'),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.db'),
            'instance/app.db',
            'app.db'
        ]
        
        for path in alternate_paths:
            if os.path.exists(path):
                print(f"Found database at alternate path: {path}")
                db_path = path
                break
        else:
            print("Could not locate database file. Please check your configuration.")
            return False
    
    print(f"Using database path: {db_path}")
    
    # Create a backup before migration
    backup_path = f"{db_path}.bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup at: {backup_path}")
    
    with open(db_path, 'rb') as src:
        with open(backup_path, 'wb') as dest:
            dest.write(src.read())
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 调试输出，检查所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Found tables: {[t[0] for t in tables]}")
    
    # PART 1: Convert is_public to visibility
    
    # Check if visibility column exists in Project table
    cursor.execute("PRAGMA table_info(project)")
    columns = [column[1].lower() for column in cursor.fetchall()]
    
    # Add visibility column if it doesn't exist
    if 'visibility' not in columns:
        print("Adding visibility column to project table...")
        cursor.execute("ALTER TABLE project ADD COLUMN visibility VARCHAR(20) DEFAULT 'private'")
        
        # Convert existing is_public values to visibility
        if 'is_public' in columns:
            print("Converting is_public values to visibility values...")
            cursor.execute("""
                UPDATE project 
                SET visibility = CASE WHEN is_public = 1 THEN 'invitation' ELSE 'private' END
            """)
    
    # PART 2: Create new tables if they don't exist
    
    # Check if friend_relationships table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='friend_relationships'")
    if not cursor.fetchone():
        print("Creating friend_relationships table...")
        cursor.execute("""
            CREATE TABLE friend_relationships (
                id INTEGER PRIMARY KEY,
                requester_id INTEGER NOT NULL,
                addressee_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(requester_id, addressee_id)
            )
        """)
        cursor.execute("CREATE INDEX idx_friend_rel_requester ON friend_relationships(requester_id)")
        cursor.execute("CREATE INDEX idx_friend_rel_addressee ON friend_relationships(addressee_id)")
    
    # Check if project_invitations table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_invitations'")
    if not cursor.fetchone():
        print("Creating project_invitations table...")
        cursor.execute("""
            CREATE TABLE project_invitations (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, invitee_id)
            )
        """)
        cursor.execute("CREATE INDEX idx_proj_inv_project ON project_invitations(project_id)")
        cursor.execute("CREATE INDEX idx_proj_inv_invitee ON project_invitations(invitee_id)")
    
    # Check if project_join_requests table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_join_requests'")
    if not cursor.fetchone():
        print("Creating project_join_requests table...")
        cursor.execute("""
            CREATE TABLE project_join_requests (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, user_id)
            )
        """)
        cursor.execute("CREATE INDEX idx_proj_req_project ON project_join_requests(project_id)")
        cursor.execute("CREATE INDEX idx_proj_req_user ON project_join_requests(user_id)")
    
    # PART 3: Remove is_public column (SQLite doesn't support DROP COLUMN directly)
    # We'll only do this if we have both visibility and is_public columns
    
    if 'visibility' in columns and 'is_public' in columns:
        print("Removing is_public column from project table...")
        
        # Get all columns except is_public
        cursor.execute("PRAGMA table_info(project)")
        columns_info = cursor.fetchall()
        columns_to_keep = [col for col in columns_info if col[1].lower() != 'is_public']
        
        # Create column definitions
        column_defs = []
        for col in columns_to_keep:
            # Format: name type constraints
            definition = f"{col[1]} {col[2]}"
            if col[5] == 1:  # Primary key
                definition += " PRIMARY KEY"
            if col[3] == 1:  # Not null
                definition += " NOT NULL"
            if col[4] is not None:  # Default value
                definition += f" DEFAULT {col[4]}"
            column_defs.append(definition)
        
        # Create column names list for SELECT
        column_names = [col[1] for col in columns_to_keep]
        
        # Create a new table without is_public
        cursor.execute(f"""
            CREATE TABLE project_new (
                {', '.join(column_defs)}
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute(f"""
            INSERT INTO project_new
            SELECT {', '.join(column_names)} FROM project
        """)
        
        # Drop old table and rename new table
        cursor.execute("DROP TABLE project")
        cursor.execute("ALTER TABLE project_new RENAME TO project")
        
        print("is_public column has been removed.")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("Migration completed successfully!")
    print(f"A backup of the original database was created at {backup_path}")
    return True

if __name__ == '__main__':
    migrate_database()