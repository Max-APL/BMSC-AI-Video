import json
from pathlib import Path
import sys
import os

# Ensure the app module can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.db_models import DBVideoMetadata, DBManualMetadata

def run_migration():
    print(f"Creating tables in {settings.storage_dir}/metadata.db...")
    Base.metadata.create_all(bind=engine)
    
    videos_dir = settings.storage_dir / "videos"
    if not videos_dir.exists():
        print("No videos directory found. Nothing to migrate.")
        return
        
    db = SessionLocal()
    
    videos_migrated = 0
    manuals_migrated = 0
    
    try:
        # Migrate Videos
        for metadata_file in videos_dir.glob("*/metadata.json"):
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            video_id = data["id"]
            existing = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == video_id).first()
            if not existing:
                record = DBVideoMetadata(**data)
                db.add(record)
                videos_migrated += 1
            else:
                print(f"Video {video_id} already exists in DB.")
                
        # Migrate Manuals
        for manual_file in videos_dir.glob("*/manuals/*/metadata.json"):
            with open(manual_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            manual_id = data["id"]
            existing = db.query(DBManualMetadata).filter(DBManualMetadata.id == manual_id).first()
            if not existing:
                record = DBManualMetadata(**data)
                db.add(record)
                manuals_migrated += 1
            else:
                print(f"Manual {manual_id} already exists in DB.")
                
        db.commit()
        print(f"Migration completed successfully. Migrated {videos_migrated} videos and {manuals_migrated} manuals.")
        
        # Opcionalmente renombrar los metadata.json a metadata.json.bak para evitar confusiones futuras
        for f in videos_dir.glob("*/metadata.json"):
            f.rename(f.with_suffix(".json.bak"))
            
        for f in videos_dir.glob("*/manuals/*/metadata.json"):
            f.rename(f.with_suffix(".json.bak"))
            
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
