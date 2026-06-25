from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
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


def ensure_sqlite_schema_columns() -> None:
    """Apply small additive SQLite migrations for deployments created before Alembic."""
    with engine.begin() as conn:
        manual_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(manuals)")).fetchall()
        }
        if manual_columns and "quality_mode" not in manual_columns:
            conn.execute(
                text("ALTER TABLE manuals ADD COLUMN quality_mode VARCHAR NOT NULL DEFAULT 'fast'")
            )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
