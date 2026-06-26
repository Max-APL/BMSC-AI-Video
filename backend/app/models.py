from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, EmailStr

class RoleBase(BaseModel):
    name: str
    permissions: List[str]
    allowed_areas: List[str] = Field(default_factory=list)

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    allowed_areas: Optional[List[str]] = None


class RoleAssignedUser(BaseModel):
    id: str
    name: Optional[str] = None
    email: EmailStr
    is_disabled: bool = False


class RoleResponse(RoleBase):
    id: str
    created_at: str
    user_count: int = 0
    assigned_users: List[RoleAssignedUser] = Field(default_factory=list)

class UserBase(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    role_id: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role_id: Optional[str] = None
    password: Optional[str] = None
    is_disabled: Optional[bool] = None

class UserResponse(UserBase):
    id: str
    created_at: str
    updated_at: Optional[str] = None
    is_disabled: bool = False
    disabled_at: Optional[str] = None
    disabled_reason: Optional[str] = None
    failed_login_attempts: int = 0
    role: Optional[RoleResponse] = None

class LoginRequest(BaseModel):
    email: str
    password: str


class VideoStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class ManualMode(str, Enum):
    extractive = "extractive"
    llm = "llm"


class ManualQualityMode(str, Enum):
    fast = "fast"
    quality = "quality"


class AnswerMode(str, Enum):
    extractive = "extractive"
    llm = "llm"


class ManualStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class VideoMetadata(BaseModel):
    id: str
    original_filename: str
    stored_filename: str
    content_type: Optional[str] = None
    status: VideoStatus
    created_at: str
    updated_at: str
    duration_seconds: Optional[float] = None
    language: Optional[str] = None
    processing_stage: Optional[str] = None
    processing_started_at: Optional[str] = None
    processing_finished_at: Optional[str] = None
    processing_progress: float = 0.0
    transcribed_seconds: float = 0.0
    transcribed_timecode: Optional[str] = None
    progress_updated_at: Optional[str] = None
    audio_extraction_backend: Optional[str] = None
    audio_extraction_error: Optional[str] = None
    segment_count: int = 0
    chunk_count: int = 0
    error: Optional[str] = None
    subarea_id: Optional[str] = None

class VideoUpdate(BaseModel):
    original_filename: Optional[str] = None
    subarea_id: Optional[str] = None


class TranscriptSegment(BaseModel):
    id: int
    start_seconds: float
    end_seconds: float
    start_timecode: str
    end_timecode: str
    text: str


class SearchChunk(BaseModel):
    id: int
    segment_ids: List[int]
    start_seconds: float
    end_seconds: float
    start_timecode: str
    end_timecode: str
    text: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Consulta del usuario")
    top_k: int = Field(5, ge=1, le=20)
    min_score: float = Field(0.05, ge=0.0, le=1.0)


class SearchMatch(SearchChunk):
    score: float


class QueryResponse(BaseModel):
    video_id: str
    query: str
    answer: Optional[str] = None
    confidence: Optional[float] = None
    matches: List[SearchMatch]


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Pregunta del usuario")
    top_k: int = Field(3, ge=1, le=10)
    min_score: float = Field(0.0, ge=0.0, le=1.0)
    mode: AnswerMode = Field(AnswerMode.extractive, description="Motor de respuesta")
    provider: Optional[str] = Field(None, description="Proveedor local del LLM")
    model: Optional[str] = Field(None, description="Modelo local para modo llm")


class AnswerResponse(BaseModel):
    video_id: str
    question: str
    answer: str
    confidence: float
    sources: List[SearchMatch]
    mode: AnswerMode = AnswerMode.extractive
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_reason: Optional[str] = None


class ManualRequest(BaseModel):
    mode: ManualMode = Field(ManualMode.llm, description="Motor de generacion")
    quality_mode: ManualQualityMode = Field(
        ManualQualityMode.fast,
        description="Perfil de generacion: rapido o calidad",
    )
    format: str = Field("markdown", description="Formato base de salida")
    provider: Optional[str] = Field(None, description="Proveedor local del LLM")
    model: Optional[str] = Field(None, description="Modelo local para modo llm")
    include_timestamps: bool = True
    include_screenshots: bool = True


class ManualMetadata(BaseModel):
    id: str
    video_id: str
    mode: ManualMode
    quality_mode: ManualQualityMode = ManualQualityMode.fast
    status: ManualStatus
    format: str = "markdown"
    provider: Optional[str] = None
    model: Optional[str] = None
    include_timestamps: bool = True
    include_screenshots: bool = True
    title: str
    filename: str
    created_at: str
    updated_at: str
    processing_started_at: Optional[str] = None
    processing_finished_at: Optional[str] = None
    processing_stage: Optional[str] = None
    progress: float = 0.0
    current_section: Optional[str] = None
    last_generated_text: Optional[str] = None
    section_count: int = 0
    word_count: int = 0
    screenshot_count: int = 0
    error: Optional[str] = None


class ManualResponse(BaseModel):
    metadata: ManualMetadata
    content: Optional[str] = None


class TranscriptResponse(BaseModel):
    video_id: str
    segments: List[TranscriptSegment]


class HealthResponse(BaseModel):
    status: str


class FfmpegStatus(BaseModel):
    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None


class SystemDependenciesResponse(BaseModel):
    ffmpeg: FfmpegStatus
    inference_device: str
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    whisper_audio_chunk_seconds: int
    whisper_beam_size: int
    whisper_best_of: int
    whisper_temperature: float
    whisper_condition_on_previous_text: bool
    whisper_cpu_threads: int
    whisper_num_workers: int
    whisper_chunk_workers: int
    llm_n_gpu_layers: int
    llm_n_threads: int
    llm_n_threads_batch: int
    llm_n_batch: int
    llm_n_ubatch: int
    llm_num_ctx: int
    llm_max_tokens_answer: int
    llm_max_tokens_section: int
