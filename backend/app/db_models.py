from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class DBRole(Base):
    __tablename__ = "roles"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    permissions = Column(String, nullable=False) # JSON encoded list of permissions
    allowed_areas = Column(String, nullable=True) # JSON encoded list of area IDs or ["*"] for all
    created_at = Column(String, nullable=False)

class DBUser(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role_id = Column(String, ForeignKey("roles.id"), nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=True)
    is_disabled = Column(Boolean, nullable=False, default=False)
    disabled_at = Column(String, nullable=True)
    disabled_reason = Column(String, nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(String, nullable=True)
    force_password_change = Column(Boolean, nullable=False, default=False)
    password_changed_at = Column(String, nullable=True)
    token_version = Column(Integer, nullable=False, default=0)

class DBAuthCode(Base):
    __tablename__ = "auth_codes"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    purpose = Column(String, index=True, nullable=False)
    code_hash = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

class DBArea(Base):
    __tablename__ = "areas"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(String, nullable=False)

class DBSubArea(Base):
    __tablename__ = "subareas"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    area_id = Column(String, ForeignKey("areas.id"), nullable=False)
    created_at = Column(String, nullable=False)

class DBVideoMetadata(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    language = Column(String, nullable=True)
    processing_stage = Column(String, nullable=True)
    processing_started_at = Column(String, nullable=True)
    processing_finished_at = Column(String, nullable=True)
    processing_progress = Column(Float, default=0.0)
    transcribed_seconds = Column(Float, default=0.0)
    transcribed_timecode = Column(String, nullable=True)
    progress_updated_at = Column(String, nullable=True)
    audio_extraction_backend = Column(String, nullable=True)
    audio_extraction_error = Column(String, nullable=True)
    segment_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    error = Column(String, nullable=True)
    subarea_id = Column(String, ForeignKey("subareas.id"), nullable=True)


class DBManualMetadata(Base):
    __tablename__ = "manuals"

    id = Column(String, primary_key=True, index=True)
    video_id = Column(String, ForeignKey("videos.id"), index=True, nullable=False)
    mode = Column(String, nullable=False)
    quality_mode = Column(String, nullable=False, default="fast")
    status = Column(String, nullable=False)
    format = Column(String, default="markdown")
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    include_timestamps = Column(Boolean, default=True)
    include_screenshots = Column(Boolean, default=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    processing_started_at = Column(String, nullable=True)
    processing_finished_at = Column(String, nullable=True)
    processing_stage = Column(String, nullable=True)
    progress = Column(Float, default=0.0)
    current_section = Column(String, nullable=True)
    last_generated_text = Column(String, nullable=True)
    section_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    screenshot_count = Column(Integer, default=0)
    error = Column(String, nullable=True)
