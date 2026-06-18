from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# Create storage directory if it doesn't exist
settings.storage_dir.mkdir(parents=True, exist_ok=True)

# URL for SQLite database inside the storage directory
DATABASE_URL = f"sqlite:///{settings.storage_dir}/metadata.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
