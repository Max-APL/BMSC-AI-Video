from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_path(name: str) -> Optional[Path]:
    value = os.getenv(name)
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _env_path_with_default(name: str, default: Path) -> Path:
    value = os.getenv(name)
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _env_origins(name: str, default: str) -> Tuple[str, ...]:
    raw_value = os.getenv(name, default)
    origins = tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())
    return origins or ("*",)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "BMSC AI Video Backend")
    storage_dir: Path = _env_path_with_default("VIDEO_STORAGE_DIR", BASE_DIR / "storage")
    ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg").strip().strip("\"'")

    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    whisper_language: Optional[str] = os.getenv("WHISPER_LANGUAGE") or None
    whisper_model_dir: Optional[Path] = _env_path("WHISPER_MODEL_DIR")

    search_chunk_seconds: int = _env_int("SEARCH_CHUNK_SECONDS", 14)
    search_chunk_max_chars: int = _env_int("SEARCH_CHUNK_MAX_CHARS", 320)

    cors_origins: Tuple[str, ...] = _env_origins(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    )


settings = Settings()
