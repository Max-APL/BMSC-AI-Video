import sqlite3
from pathlib import Path
import sys
import os
import uuid
import datetime
import bcrypt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

def run_migration():
    db_path = settings.storage_dir / "metadata.db"
    if not db_path.exists():
        print("Database not found. Make sure it is created.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if subarea_id exists in videos
        cursor.execute("PRAGMA table_info(videos)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "subarea_id" not in columns:
            print("Adding subarea_id to videos table...")
            cursor.execute("ALTER TABLE videos ADD COLUMN subarea_id VARCHAR REFERENCES subareas(id)")
        else:
            print("subarea_id already exists in videos table.")
            
        # We also need to create tables if they don't exist. We'll do this via SQLAlchemy in main.py startup, 
        # but let's do it here just to be safe.
        from app.database import Base, engine
        Base.metadata.create_all(bind=engine)
        
        # Create default admin user
        cursor.execute("SELECT id FROM users WHERE email = ?", ("admin@bmsc.com.bo",))
        if not cursor.fetchone():
            print("Creating default admin user...")
            user_id = str(uuid.uuid4())
            hashed_password = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            now = datetime.datetime.utcnow().isoformat()
            cursor.execute(
                "INSERT INTO users (id, email, hashed_password, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, "admin@bmsc.com.bo", hashed_password, 1, now)
            )
            
        conn.commit()
        print("Migration successful.")
    except Exception as e:
        conn.rollback()
        print(f"Error migrating database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
