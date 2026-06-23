from __future__ import annotations

import mimetypes
import traceback
import uuid
from urllib.parse import unquote
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple

from fastapi import UploadFile

from .answering import build_extractive_answer
from .chunking import build_search_chunks
from .config import Settings
from .debug import log_event
from .manual_exports import ManualExportError, export_manual
from .manual_generation import (
    build_extractive_manual,
    build_llm_manual,
    build_text_blocks,
    build_time_blocks,
    compact_datetime_lapaz,
    count_words,
    manual_title,
)
from .models import (
    AnswerResponse,
    ManualMetadata,
    ManualMode,
    ManualRequest,
    ManualResponse,
    ManualStatus,
    QueryResponse,
    SearchMatch,
    SystemDependenciesResponse,
    TranscriptResponse,
    VideoMetadata,
    VideoStatus,
)
from .search import TfidfSearchEngine
from .screenshots import build_screenshot_targets, extract_manual_screenshots
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
        self._manual_lock = Lock()

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

    def get_video_media(self, video_id: str) -> Tuple[Path, str, str]:
        metadata = self.storage.load_metadata(video_id)
        source_path = self.storage.source_path(metadata)
        if not source_path.exists():
            raise FileNotFoundError(video_id)

        guessed_type = mimetypes.guess_type(metadata.original_filename)[0]
        media_type = metadata.content_type or guessed_type or "application/octet-stream"
        return source_path, media_type, metadata.original_filename

    def create_manual(self, video_id: str, request: ManualRequest) -> ManualMetadata:
        if request.format != "markdown":
            raise ValueError("Formato no soportado. Usa format='markdown'.")

        video = self.storage.load_metadata(video_id)
        if video.status != VideoStatus.ready:
            raise RuntimeError(
                f"El video no esta listo para generar manuales. Estado actual: {video.status.value}"
            )

        segments = self.storage.load_transcript(video_id)
        if not segments:
            raise RuntimeError("No hay transcripcion disponible para generar el manual.")

        provider = request.provider or self.settings.llm_provider
        model = request.model or self.settings.llm_model
        if request.mode == ManualMode.extractive:
            provider = None
            model = None

        manual_id = uuid.uuid4().hex
        now = utc_now()
        metadata = ManualMetadata(
            id=manual_id,
            video_id=video_id,
            mode=request.mode,
            status=ManualStatus.queued,
            format=request.format,
            provider=provider,
            model=model,
            include_timestamps=request.include_timestamps,
            include_screenshots=request.include_screenshots,
            title=manual_title(video),
            filename=f"manual-{request.mode.value}-{compact_datetime_lapaz(now)}-{manual_id[:8]}.md",
            created_at=now,
            updated_at=now,
        )
        self.storage.save_manual_metadata(metadata)
        log_event(
            "Manual generation queued "
            f"mode={metadata.mode.value} provider={metadata.provider} model={metadata.model}",
            video_id,
        )
        return metadata

    def process_manual(self, video_id: str, manual_id: str) -> None:
        log_event(f"Manual processing requested manual_id={manual_id}", video_id)
        with self._manual_lock:
            log_event(f"Manual lock acquired manual_id={manual_id}", video_id)
            self._process_manual_locked(video_id, manual_id)

    def _process_manual_locked(self, video_id: str, manual_id: str) -> None:
        metadata = self.storage.update_manual_metadata(
            video_id,
            manual_id,
            status=ManualStatus.processing,
            processing_started_at=utc_now(),
            processing_finished_at=None,
            processing_stage="preparing",
            progress=1.0,
            current_section=None,
            last_generated_text=None,
            error=None,
        )
        try:
            video = self.storage.load_metadata(video_id)
            segments = self.storage.load_transcript(video_id)
            if not segments:
                raise RuntimeError("No hay transcripcion disponible para generar el manual.")

            screenshots_by_block: Dict[int, List[Tuple[str, str]]] = {}
            if metadata.include_screenshots:
                self.storage.update_manual_metadata(
                    video_id,
                    manual_id,
                    processing_stage="extracting_screenshots",
                    progress=8.0,
                    current_section="Extrayendo capturas del video",
                )
                manual_blocks = (
                    build_text_blocks(
                        segments,
                        chunk_seconds=self.settings.manual_llm_chunk_seconds,
                        max_chars=self.settings.manual_llm_chunk_max_chars,
                    )
                    if metadata.mode == ManualMode.llm
                    else build_time_blocks(segments, chunk_seconds=self.settings.manual_chunk_seconds)
                )
                screenshot_max_count = self.resolve_manual_screenshot_max_count(
                    metadata.mode,
                    manual_blocks,
                )
                screenshot_targets = build_screenshot_targets(
                    segments=segments,
                    parent_blocks=manual_blocks,
                    max_count=screenshot_max_count,
                    key_points_only=metadata.mode == ManualMode.llm,
                    min_gap_seconds=self.settings.manual_screenshot_min_gap_seconds,
                )
                screenshots = extract_manual_screenshots(
                    video_path=self.storage.source_path(video),
                    output_dir=self.storage.manual_screenshots_dir(video_id, manual_id),
                    blocks=screenshot_targets,
                    ffmpeg_bin=self.settings.ffmpeg_bin,
                    offset_seconds=self.settings.manual_screenshot_offset_seconds,
                    width=self.settings.manual_screenshot_width,
                    max_count=screenshot_max_count,
                )
                for screenshot in screenshots:
                    screenshots_by_block.setdefault(screenshot.block_index, []).append(
                        (screenshot.relative_path, screenshot.caption)
                    )
                self.storage.update_manual_metadata(
                    video_id,
                    manual_id,
                    screenshot_count=sum(len(items) for items in screenshots_by_block.values()),
                    progress=18.0,
                    current_section=f"{sum(len(items) for items in screenshots_by_block.values())} capturas extraidas",
                )
                log_event(
                    "Manual screenshots extracted "
                    f"manual_id={manual_id} count={sum(len(items) for items in screenshots_by_block.values())}",
                    video_id,
                )

            if metadata.mode == ManualMode.extractive:
                self.storage.update_manual_metadata(
                    video_id,
                    manual_id,
                    processing_stage="building_extractive_manual",
                    progress=35.0 if metadata.include_screenshots else 20.0,
                )
                result = build_extractive_manual(
                    video,
                    segments,
                    chunk_seconds=self.settings.manual_chunk_seconds,
                    include_timestamps=metadata.include_timestamps,
                    generated_at=metadata.created_at,
                    screenshots_by_block=screenshots_by_block,
                )
            elif metadata.mode == ManualMode.llm:
                self.storage.update_manual_metadata(
                    video_id,
                    manual_id,
                    processing_stage="generating_with_llm",
                    progress=20.0 if metadata.include_screenshots else 5.0,
                )
                progress_state = {"last_saved_length": 0}

                def save_llm_progress(content: str, block_index: int, total_blocks: int, delta: str) -> None:
                    content_length = len(content)
                    if delta and content_length - progress_state["last_saved_length"] < 160:
                        return
                    progress_state["last_saved_length"] = content_length
                    base_progress = 20.0 if metadata.include_screenshots else 5.0
                    progress = base_progress
                    if total_blocks > 0 and block_index > 0:
                        ratio = min(1.0, max(0.0, (block_index - 0.35) / total_blocks))
                        progress = min(98.0, round(base_progress + (ratio * (98.0 - base_progress)), 2))
                    self.storage.save_manual_content(video_id, manual_id, content)
                    self.storage.update_manual_metadata(
                        video_id,
                        manual_id,
                        processing_stage="generating_with_llm",
                        progress=progress,
                        current_section=(
                            f"Bloque {block_index} de {total_blocks}"
                            if block_index > 0
                            else f"Preparando {total_blocks} bloques"
                        ),
                        last_generated_text=(delta or content[-240:])[-240:],
                        word_count=count_words(content),
                    )

                result = build_llm_manual(
                    video,
                    segments,
                    settings=self.settings,
                    provider=metadata.provider or self.settings.llm_provider,
                    model=metadata.model or self.settings.llm_model,
                    include_timestamps=metadata.include_timestamps,
                    generated_at=metadata.created_at,
                    screenshots_by_block=screenshots_by_block,
                    on_progress=save_llm_progress,
                )
            else:
                raise RuntimeError(f"Modo de manual no soportado: {metadata.mode}")

            self.storage.save_manual_content(video_id, manual_id, result.content)
            self.storage.update_manual_metadata(
                video_id,
                manual_id,
                status=ManualStatus.ready,
                processing_finished_at=utc_now(),
                processing_stage="ready",
                progress=100.0,
                current_section=None,
                last_generated_text=None,
                section_count=result.section_count,
                word_count=result.word_count,
                screenshot_count=sum(len(items) for items in screenshots_by_block.values()),
                error=None,
            )
            log_event(
                "Manual generation finished "
                f"manual_id={manual_id} sections={result.section_count} words={result.word_count}",
                video_id,
            )
        except Exception as exc:
            log_event(f"Manual generation failed manual_id={manual_id} error={exc}", video_id)
            print(traceback.format_exc(), flush=True)
            self.storage.update_manual_metadata(
                video_id,
                manual_id,
                status=ManualStatus.failed,
                processing_finished_at=utc_now(),
                processing_stage="failed",
                error=str(exc),
            )

    def resolve_manual_screenshot_max_count(
        self,
        mode: ManualMode,
        manual_blocks: List,
    ) -> int:
        if not manual_blocks:
            return 0
        if mode == ManualMode.llm:
            configured_limit = self.settings.manual_llm_screenshot_max_count
            if configured_limit > 0:
                return configured_limit
            return 0

        configured_limit = self.settings.manual_screenshot_max_count
        if configured_limit > 0:
            return configured_limit
        return 0

    def list_manuals(self, video_id: str) -> List[ManualMetadata]:
        self.storage.load_metadata(video_id)
        return self.storage.list_manual_metadata(video_id)

    def get_manual(self, video_id: str, manual_id: str, include_content: bool = False) -> ManualResponse:
        metadata = self.storage.load_manual_metadata(video_id, manual_id)
        content = None
        if include_content:
            content = self.storage.load_manual_content(video_id, manual_id)
        return ManualResponse(metadata=metadata, content=content)

    def get_manual_file(self, video_id: str, manual_id: str, output_format: str) -> Tuple[Path, str, str]:
        metadata = self.storage.load_manual_metadata(video_id, manual_id)
        if metadata.status != ManualStatus.ready:
            raise RuntimeError(f"El manual aun no esta listo. Estado actual: {metadata.status.value}")
        output_format = output_format.lower()
        content_path = self.storage.manual_content_path(video_id, manual_id)
        if not content_path.exists():
            raise FileNotFoundError(manual_id)
        content = self.storage.load_manual_content(video_id, manual_id)
        export_path = self.storage.manual_export_path(video_id, manual_id, output_format)
        try:
            path = export_manual(
                content,
                export_path,
                output_format,
                assets_dir=self.storage.manual_assets_dir(video_id, manual_id),
            )
        except ManualExportError:
            raise
        suffix = "md" if output_format == "markdown" else output_format
        media_types = {
            "markdown": "text/markdown; charset=utf-8",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
        }
        filename = f"{Path(metadata.filename).stem}.{suffix}"
        return path, filename, media_types.get(output_format, "application/octet-stream")

    def get_manual_asset(self, video_id: str, manual_id: str, asset_path: str) -> Tuple[Path, str, str]:
        self.storage.load_manual_metadata(video_id, manual_id)
        normalized = unquote(asset_path).replace("\\", "/").strip("/")
        parts = [part for part in normalized.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            raise FileNotFoundError(asset_path)

        root = self.storage.manual_assets_dir(video_id, manual_id).resolve()
        path = (root / Path(*parts)).resolve()
        if root not in path.parents and path != root:
            raise FileNotFoundError(asset_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(asset_path)

        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path, media_type, path.name

    def delete_manual(self, video_id: str, manual_id: str) -> None:
        self.storage.delete_manual(video_id, manual_id)

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
            whisper_audio_chunk_seconds=self.settings.whisper_audio_chunk_seconds,
            whisper_beam_size=self.settings.whisper_beam_size,
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
