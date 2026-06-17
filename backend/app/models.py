from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    uploaded = "uploaded"
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


class AnswerResponse(BaseModel):
    video_id: str
    question: str
    answer: str
    confidence: float
    sources: List[SearchMatch]


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
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
