from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import UploadFile

from .config import Settings
from .models import ManualMetadata, SearchChunk, TranscriptSegment, VideoMetadata, VideoStatus, ManualStatus, ManualMode
from .database import get_db, SessionLocal
from .db_models import DBVideoMetadata, DBManualMetadata


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "video").name.strip() or "video"
    safe = "".join(char if char.isalnum() or char in "._- " else "_" for char in name)
    return safe.strip(" .") or "video"


class VideoStorage:
    def __init__(self, settings: Settings):
        self.root = settings.storage_dir
        self.videos_dir = self.root / "videos"
        self.videos_dir.mkdir(parents=True, exist_ok=True)

    def _get_db_session(self):
        return SessionLocal()

    def video_dir(self, video_id: str) -> Path:
        return self.videos_dir / video_id

    def transcript_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "transcript.json"

    def chunks_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "chunks.json"

    def audio_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "audio.wav"

    def thumbnail_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "thumbnail.jpg"

    def source_path(self, metadata: VideoMetadata) -> Path:
        return self.video_dir(metadata.id) / metadata.stored_filename

    def manuals_dir(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "manuals"

    def manual_content_path(self, video_id: str, manual_id: str) -> Path:
        return self.manuals_dir(video_id) / manual_id / "manual.md"

    def manual_export_path(self, video_id: str, manual_id: str, output_format: str) -> Path:
        suffix = "md" if output_format == "markdown" else output_format
        return self.manuals_dir(video_id) / manual_id / f"manual.{suffix}"

    def manual_assets_dir(self, video_id: str, manual_id: str) -> Path:
        return self.manuals_dir(video_id) / manual_id

    def manual_screenshots_dir(self, video_id: str, manual_id: str) -> Path:
        return self.manual_assets_dir(video_id, manual_id) / "screenshots"

    def manual_screenshot_path(self, video_id: str, manual_id: str, filename: str) -> Path:
        return self.manual_screenshots_dir(video_id, manual_id) / filename

    async def create_video(self, upload: UploadFile) -> VideoMetadata:
        original_filename = sanitize_filename(upload.filename or "video")
        suffix = Path(original_filename).suffix.lower()
        video_id = uuid.uuid4().hex
        video_dir = self.video_dir(video_id)
        video_dir.mkdir(parents=True, exist_ok=False)

        stored_filename = f"source{suffix}" if suffix else "source"
        destination = video_dir / stored_filename

        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)

        now = utc_now()
        metadata = VideoMetadata(
            id=video_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=upload.content_type,
            status=VideoStatus.uploaded,
            created_at=now,
            updated_at=now,
        )
        self.save_metadata(metadata)
        return metadata

    def list_metadata(self) -> List[VideoMetadata]:
        with self._get_db_session() as db:
            records = db.query(DBVideoMetadata).all()
            return [self._db_to_video_metadata(r) for r in records]

    def load_metadata(self, video_id: str) -> VideoMetadata:
        with self._get_db_session() as db:
            record = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == video_id).first()
            if not record:
                raise FileNotFoundError(video_id)
            return self._db_to_video_metadata(record)

    def save_metadata(self, metadata: VideoMetadata) -> None:
        with self._get_db_session() as db:
            data = model_to_dict(metadata)
            record = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == metadata.id).first()
            if not record:
                record = DBVideoMetadata(**data)
                db.add(record)
            else:
                for key, value in data.items():
                    setattr(record, key, value)
            db.commit()

    def update_metadata(self, video_id: str, **updates) -> VideoMetadata:
        metadata = self.load_metadata(video_id)
        data = model_to_dict(metadata)
        data.update(updates)
        data["updated_at"] = utc_now()
        updated = VideoMetadata(**data)
        self.save_metadata(updated)
        return updated

    def save_transcript(self, video_id: str, segments: Iterable[TranscriptSegment]) -> None:
        self._write_json(
            self.transcript_path(video_id),
            [model_to_dict(segment) for segment in segments],
        )

    def load_transcript(self, video_id: str) -> List[TranscriptSegment]:
        path = self.transcript_path(video_id)
        if not path.exists():
            return []
        return [TranscriptSegment(**item) for item in self._read_json(path)]

    def save_chunks(self, video_id: str, chunks: Iterable[SearchChunk]) -> None:
        self._write_json(
            self.chunks_path(video_id),
            [model_to_dict(chunk) for chunk in chunks],
        )

    def load_chunks(self, video_id: str) -> List[SearchChunk]:
        path = self.chunks_path(video_id)
        if not path.exists():
            return []
        return [SearchChunk(**item) for item in self._read_json(path)]

    def save_manual_metadata(self, metadata: ManualMetadata) -> None:
        with self._get_db_session() as db:
            data = model_to_dict(metadata)
            record = db.query(DBManualMetadata).filter(DBManualMetadata.id == metadata.id).first()
            if not record:
                record = DBManualMetadata(**data)
                db.add(record)
            else:
                for key, value in data.items():
                    setattr(record, key, value)
            db.commit()

    def load_manual_metadata(self, video_id: str, manual_id: str) -> ManualMetadata:
        with self._get_db_session() as db:
            record = db.query(DBManualMetadata).filter(DBManualMetadata.id == manual_id, DBManualMetadata.video_id == video_id).first()
            if not record:
                raise FileNotFoundError(manual_id)
            return self._db_to_manual_metadata(record)

    def list_manual_metadata(self, video_id: str) -> List[ManualMetadata]:
        with self._get_db_session() as db:
            records = db.query(DBManualMetadata).filter(DBManualMetadata.video_id == video_id).all()
            return [self._db_to_manual_metadata(r) for r in records]

    def update_manual_metadata(self, video_id: str, manual_id: str, **updates) -> ManualMetadata:
        metadata = self.load_manual_metadata(video_id, manual_id)
        data = model_to_dict(metadata)
        data.update(updates)
        data["updated_at"] = utc_now()
        updated = ManualMetadata(**data)
        self.save_manual_metadata(updated)
        return updated

    def save_manual_content(self, video_id: str, manual_id: str, content: str) -> None:
        path = self.manual_content_path(video_id, manual_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        self._replace_with_retry(temp_path, path)

    def load_manual_content(self, video_id: str, manual_id: str) -> str:
        path = self.manual_content_path(video_id, manual_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def delete_manual(self, video_id: str, manual_id: str) -> None:
        with self._get_db_session() as db:
            record = db.query(DBManualMetadata).filter(DBManualMetadata.id == manual_id, DBManualMetadata.video_id == video_id).first()
            if not record:
                raise FileNotFoundError(manual_id)
            db.delete(record)
            db.commit()

        path = self.manual_assets_dir(video_id, manual_id)
        if path.exists():
            shutil.rmtree(path)

    def delete_video(self, video_id: str) -> None:
        with self._get_db_session() as db:
            # Delete manual records
            manuals = db.query(DBManualMetadata).filter(DBManualMetadata.video_id == video_id).all()
            for m in manuals:
                db.delete(m)
            # Delete video record
            record = db.query(DBVideoMetadata).filter(DBVideoMetadata.id == video_id).first()
            if not record:
                raise FileNotFoundError(video_id)
            db.delete(record)
            db.commit()

        path = self.video_dir(video_id)
        if path.exists():
            shutil.rmtree(path)

    def _read_json(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._replace_with_retry(temp_path, path)

    def _replace_with_retry(self, temp_path: Path, target_path: Path) -> None:
        last_error: PermissionError | None = None
        for delay in (0.02, 0.05, 0.1, 0.2, 0.4):
            try:
                temp_path.replace(target_path)
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(delay)
        try:
            temp_path.replace(target_path)
        except PermissionError as exc:
            raise last_error or exc

    def _db_to_video_metadata(self, record: DBVideoMetadata) -> VideoMetadata:
        data = {c.name: getattr(record, c.name) for c in record.__table__.columns}
        return VideoMetadata(**data)

    def _db_to_manual_metadata(self, record: DBManualMetadata) -> ManualMetadata:
        data = {c.name: getattr(record, c.name) for c in record.__table__.columns}
        return ManualMetadata(**data)
