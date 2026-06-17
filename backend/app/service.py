from __future__ import annotations

import traceback
from pathlib import Path
from threading import Lock
from typing import List

from fastapi import UploadFile

from .answering import build_extractive_answer
from .chunking import build_search_chunks
from .config import Settings
from .debug import log_event
from .models import (
    QueryResponse,
    SearchMatch,
    AnswerResponse,
    SystemDependenciesResponse,
    TranscriptResponse,
    VideoMetadata,
    VideoStatus,
)
from .search import TfidfSearchEngine
from .storage import VideoStorage, utc_now
from .timecodes import format_timecode
from .transcription import (
    FasterWhisperTranscriber,
    TranscriptionError,
    extract_audio,
    get_ffmpeg_status,
    get_wav_duration,
)


SUPPORTED_MEDIA_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mvk",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".wav",
    ".webm",
}


class VideoService:
    def __init__(
        self,
        settings: Settings,
        storage: VideoStorage,
        transcriber: FasterWhisperTranscriber,
        search_engine: TfidfSearchEngine,
    ):
        self.settings = settings
        self.storage = storage
        self.transcriber = transcriber
        self.search_engine = search_engine
        self._processing_lock = Lock()

    async def create_video(self, upload: UploadFile) -> VideoMetadata:
        filename = upload.filename or "video"
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_MEDIA_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_MEDIA_EXTENSIONS))
            raise ValueError(f"Formato no soportado. Usa uno de: {allowed}")

        metadata = await self.storage.create_video(upload)
        source_path = self.storage.source_path(metadata)
        log_event(
            "Upload stored "
            f"filename={metadata.original_filename} "
            f"content_type={metadata.content_type} "
            f"size={source_path.stat().st_size} bytes",
            metadata.id,
        )
        return metadata

    def process_video(self, video_id: str) -> None:
        log_event("Background processing requested; setting stage=queued", video_id)
        metadata = self.storage.update_metadata(
            video_id,
            status=VideoStatus.processing,
            processing_stage="queued",
            processing_started_at=utc_now(),
            processing_finished_at=None,
            processing_progress=0.0,
            transcribed_seconds=0.0,
            transcribed_timecode=None,
            progress_updated_at=utc_now(),
            error=None,
        )
        log_event("Waiting for single-video processing lock", video_id)
        with self._processing_lock:
            log_event("Single-video processing lock acquired", video_id)
            self._process_video_locked(video_id, metadata)

    def _process_video_locked(self, video_id: str, metadata: VideoMetadata) -> None:
        log_event("Processing started", video_id)
        self.storage.update_metadata(video_id, processing_stage="starting")
        try:
            source_path = self.storage.source_path(metadata)
            audio_path = self.storage.audio_path(video_id)
            transcription_input = audio_path
            log_event(
                f"Source path={source_path} size={source_path.stat().st_size} bytes",
                video_id,
            )
            self.storage.update_metadata(video_id, processing_stage="extracting_audio")
            try:
                if not audio_path.exists() or audio_path.stat().st_mtime < source_path.stat().st_mtime:
                    log_event("Starting ffmpeg audio extraction", video_id)
                    extract_audio(source_path, audio_path, self.settings.ffmpeg_bin)
                    log_event(
                        f"ffmpeg audio extraction finished audio_size={audio_path.stat().st_size} bytes",
                        video_id,
                    )
                else:
                    log_event(
                        f"Reusing existing audio file audio_size={audio_path.stat().st_size} bytes",
                        video_id,
                    )
                duration_seconds = get_wav_duration(audio_path)
                log_event(f"Audio duration detected duration_seconds={duration_seconds}", video_id)
                self.storage.update_metadata(
                    video_id,
                    processing_stage="transcribing",
                    duration_seconds=duration_seconds,
                    processing_progress=0.0,
                    transcribed_seconds=0.0,
                    transcribed_timecode=format_timecode(0),
                    progress_updated_at=utc_now(),
                    audio_extraction_backend="ffmpeg",
                    audio_extraction_error=None,
                )
            except TranscriptionError as exc:
                transcription_input = source_path
                log_event(
                    "ffmpeg audio extraction failed; falling back to direct file transcription "
                    f"error={exc}",
                    video_id,
                )
                self.storage.update_metadata(
                    video_id,
                    processing_stage="transcribing",
                    processing_progress=0.0,
                    transcribed_seconds=0.0,
                    transcribed_timecode=format_timecode(0),
                    progress_updated_at=utc_now(),
                    audio_extraction_backend="direct",
                    audio_extraction_error=str(exc),
                )

            partial_segments: List = []

            def save_partial_transcript(segment) -> None:
                partial_segments.append(segment)
                current_metadata = self.storage.load_metadata(video_id)
                duration = current_metadata.duration_seconds or 0
                progress = 0.0
                if duration > 0:
                    progress = min(99.0, round((segment.end_seconds / duration) * 100, 2))
                if len(partial_segments) == 1 or len(partial_segments) % 10 == 0:
                    self.storage.save_transcript(video_id, partial_segments)
                    log_event(
                        "Partial transcript saved "
                        f"segments={len(partial_segments)} progress={progress}% "
                        f"timecode={segment.end_timecode}",
                        video_id,
                    )
                self.storage.update_metadata(
                    video_id,
                    segment_count=len(partial_segments),
                    transcribed_seconds=segment.end_seconds,
                    transcribed_timecode=segment.end_timecode,
                    processing_progress=progress,
                    progress_updated_at=utc_now(),
                )

            segments, language, duration = self.transcriber.transcribe(
                transcription_input,
                on_segment=save_partial_transcript,
                video_id=video_id,
            )
            log_event(f"Building search chunks from {len(segments)} transcript segments", video_id)
            self.storage.update_metadata(
                video_id,
                processing_stage="indexing",
                processing_progress=99.0,
                progress_updated_at=utc_now(),
            )
            chunks = build_search_chunks(
                segments,
                target_seconds=self.settings.search_chunk_seconds,
                max_chars=self.settings.search_chunk_max_chars,
            )

            self.storage.save_transcript(video_id, segments)
            self.storage.save_chunks(video_id, chunks)
            log_event(f"Search chunks saved chunk_count={len(chunks)}", video_id)
            self.storage.update_metadata(
                video_id,
                status=VideoStatus.ready,
                language=language,
                duration_seconds=duration,
                processing_stage="ready",
                processing_finished_at=utc_now(),
                processing_progress=100.0,
                transcribed_seconds=duration or (segments[-1].end_seconds if segments else 0.0),
                transcribed_timecode=format_timecode(duration or (segments[-1].end_seconds if segments else 0.0)),
                progress_updated_at=utc_now(),
                segment_count=len(segments),
                chunk_count=len(chunks),
                error=None,
            )
            log_event("Processing finished successfully; status=ready", video_id)
        except Exception as exc:
            log_event(f"Processing failed error={exc}", video_id)
            print(traceback.format_exc(), flush=True)
            self.storage.update_metadata(
                video_id,
                status=VideoStatus.failed,
                processing_stage="failed",
                processing_finished_at=utc_now(),
                progress_updated_at=utc_now(),
                error=str(exc),
            )

    def get_video(self, video_id: str) -> VideoMetadata:
        return self.storage.load_metadata(video_id)

    def list_videos(self) -> List[VideoMetadata]:
        return self.storage.list_metadata()

    def get_transcript(self, video_id: str) -> TranscriptResponse:
        metadata = self.storage.load_metadata(video_id)
        segments = self.storage.load_transcript(video_id)
        if metadata.status != VideoStatus.ready and not segments:
            raise RuntimeError(
                "La transcripcion aun no esta disponible. "
                f"Estado actual: {metadata.status.value}; etapa: {metadata.processing_stage or 'sin iniciar'}."
            )
        return TranscriptResponse(
            video_id=video_id,
            segments=segments,
        )

    def query_video(
        self,
        video_id: str,
        query: str,
        top_k: int,
        min_score: float,
    ) -> QueryResponse:
        metadata = self.storage.load_metadata(video_id)
        if metadata.status != VideoStatus.ready:
            raise RuntimeError(
                f"El video no esta listo para consultas. Estado actual: {metadata.status.value}"
            )

        chunks = self.storage.load_chunks(video_id)
        matches: List[SearchMatch] = self.search_engine.search(
            chunks,
            query=query,
            top_k=top_k,
            min_score=min_score,
        )
        answer = build_extractive_answer(video_id=video_id, question=query, matches=matches)
        return QueryResponse(
            video_id=video_id,
            query=query,
            answer=answer.answer,
            confidence=answer.confidence,
            matches=matches,
        )

    def answer_video(
        self,
        video_id: str,
        question: str,
        top_k: int,
        min_score: float,
    ) -> AnswerResponse:
        query_response = self.query_video(
            video_id=video_id,
            query=question,
            top_k=top_k,
            min_score=min_score,
        )
        return build_extractive_answer(
            video_id=video_id,
            question=question,
            matches=query_response.matches,
        )

    def reindex_video(self, video_id: str) -> VideoMetadata:
        metadata = self.storage.load_metadata(video_id)
        segments = self.storage.load_transcript(video_id)
        if not segments:
            raise RuntimeError("No hay transcripcion para reconstruir el indice.")

        chunks = build_search_chunks(
            segments,
            target_seconds=self.settings.search_chunk_seconds,
            max_chars=self.settings.search_chunk_max_chars,
        )
        self.storage.save_chunks(video_id, chunks)
        return self.storage.update_metadata(
            video_id,
            chunk_count=len(chunks),
            error=None if metadata.status == VideoStatus.ready else metadata.error,
        )

    def delete_video(self, video_id: str) -> None:
        self.storage.delete_video(video_id)

    def get_system_dependencies(self) -> SystemDependenciesResponse:
        return SystemDependenciesResponse(
            ffmpeg=get_ffmpeg_status(self.settings.ffmpeg_bin),
            whisper_model=self.settings.whisper_model,
            whisper_device=self.settings.whisper_device,
            whisper_compute_type=self.settings.whisper_compute_type,
        )

    def recover_interrupted_processing(self) -> int:
        recovered = 0
        for metadata in self.storage.list_metadata():
            if metadata.status != VideoStatus.processing:
                continue
            log_event("Recovered interrupted processing state; marking as failed", metadata.id)
            self.storage.update_metadata(
                metadata.id,
                status=VideoStatus.failed,
                processing_stage="interrupted",
                processing_finished_at=utc_now(),
                progress_updated_at=utc_now(),
                error=(
                    "El procesamiento quedo interrumpido por un reinicio o cierre del "
                    "backend. Ejecuta POST /videos/{video_id}/process para reprocesar."
                ),
            )
            recovered += 1
        return recovered
