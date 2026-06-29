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

        user_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        user_migrations = {
            "failed_login_attempts": "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0",
            "locked_until": "ALTER TABLE users ADD COLUMN locked_until VARCHAR",
            "force_password_change": "ALTER TABLE users ADD COLUMN force_password_change BOOLEAN NOT NULL DEFAULT 0",
            "password_changed_at": "ALTER TABLE users ADD COLUMN password_changed_at VARCHAR",
            "token_version": "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0",
        }
        for column, statement in user_migrations.items():
            if user_columns and column not in user_columns:
                conn.execute(text(statement))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
