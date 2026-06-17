from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from fastapi import UploadFile

from .config import Settings
from .models import SearchChunk, TranscriptSegment, VideoMetadata, VideoStatus


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

    def video_dir(self, video_id: str) -> Path:
        return self.videos_dir / video_id

    def metadata_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "metadata.json"

    def transcript_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "transcript.json"

    def chunks_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "chunks.json"

    def audio_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "audio.wav"

    def source_path(self, metadata: VideoMetadata) -> Path:
        return self.video_dir(metadata.id) / metadata.stored_filename

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
        metadata_items: List[VideoMetadata] = []
        for path in sorted(self.videos_dir.glob("*/metadata.json")):
            metadata_items.append(VideoMetadata(**self._read_json(path)))
        return metadata_items

    def load_metadata(self, video_id: str) -> VideoMetadata:
        path = self.metadata_path(video_id)
        if not path.exists():
            raise FileNotFoundError(video_id)
        return VideoMetadata(**self._read_json(path))

    def save_metadata(self, metadata: VideoMetadata) -> None:
        self._write_json(self.metadata_path(metadata.id), model_to_dict(metadata))

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

    def delete_video(self, video_id: str) -> None:
        path = self.video_dir(video_id)
        if not path.exists():
            raise FileNotFoundError(video_id)
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
        temp_path.replace(path)
