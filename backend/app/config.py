from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str((BASE_DIR / "models_cache" / "huggingface").resolve()))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

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


def _env_auto_int(name: str, default: int) -> int:
    value = _env_int(name, default)
    return default if value <= 0 else value


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configured_inference_device() -> Optional[str]:
    value = os.getenv("INFERENCE_DEVICE")
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"cpu", "cuda"}:
        return normalized
    return "cpu"


def _default_whisper_device() -> str:
    return (
        _configured_inference_device()
        or os.getenv("WHISPER_DEVICE", "cpu").strip()
        or "cpu"
    )


def _default_whisper_compute_type() -> str:
    value = os.getenv("WHISPER_COMPUTE_TYPE")
    if value and value.strip():
        return value.strip()
    return "float16" if _configured_inference_device() == "cuda" else "int8"


def _default_llm_gpu_layers() -> int:
    device = _configured_inference_device()
    if device == "cpu":
        return 0
    if device == "cuda":
        return -1
    return _env_int("LLM_N_GPU_LAYERS", -1)


def _effective_inference_device() -> str:
    device = _configured_inference_device()
    if device:
        return device
    whisper_device = _default_whisper_device().strip().lower()
    llm_gpu_layers = _default_llm_gpu_layers()
    if whisper_device == "cpu" and llm_gpu_layers == 0:
        return "cpu"
    if whisper_device == "cuda" and llm_gpu_layers != 0:
        return "cuda"
    return "custom"


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


def _env_optional_language(name: str) -> Optional[str]:
    value = os.getenv(name)
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"auto", "und", "unknown", "none", "null"}:
        return None
    return value.strip()


def _env_origins(name: str, default: str) -> Tuple[str, ...]:
    raw_value = os.getenv(name, default)
    origins = tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())
    return origins or ("*",)


def _cpu_count() -> int:
    return max(1, os.cpu_count() or 4)


def _default_model_threads() -> int:
    cpus = _cpu_count()
    if cpus <= 2:
        return 1
    if cpus <= 4:
        return cpus - 1
    if cpus <= 8:
        return cpus - 2
    if cpus <= 16:
        return min(12, cpus - 4)
    return 12


def _default_whisper_threads() -> int:
    cpus = _cpu_count()
    if cpus <= 2:
        return 1
    if cpus <= 4:
        return cpus - 1
    if cpus <= 8:
        return cpus - 2
    return 8


def _default_batch_threads() -> int:
    return min(32, _cpu_count())


def _default_llm_batch() -> int:
    cpus = _cpu_count()
    if cpus < 8:
        return 512
    return 1024


def _default_llm_context() -> int:
    return 4096


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "BMSC AI Video Backend")
    storage_dir: Path = _env_path_with_default("VIDEO_STORAGE_DIR", BASE_DIR / "storage")
    ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg").strip().strip("\"'")

    inference_device: str = _effective_inference_device()
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    whisper_device: str = _default_whisper_device()
    whisper_compute_type: str = _default_whisper_compute_type()
    whisper_language: Optional[str] = _env_optional_language("WHISPER_LANGUAGE")
    whisper_model_dir: Optional[Path] = _env_path("WHISPER_MODEL_DIR")
    whisper_audio_chunk_seconds: int = _env_int("WHISPER_AUDIO_CHUNK_SECONDS", 300)
    whisper_beam_size: int = _env_int("WHISPER_BEAM_SIZE", 5)
    whisper_best_of: int = _env_int("WHISPER_BEST_OF", 5)
    whisper_temperature: float = _env_float("WHISPER_TEMPERATURE", 0.0)
    whisper_condition_on_previous_text: bool = _env_bool("WHISPER_CONDITION_ON_PREVIOUS_TEXT", True)
    whisper_cpu_threads: int = _env_auto_int("WHISPER_CPU_THREADS", _default_whisper_threads())
    whisper_num_workers: int = _env_auto_int("WHISPER_NUM_WORKERS", 1)
    whisper_chunk_workers: int = _env_int("WHISPER_CHUNK_WORKERS", 1)

    search_chunk_seconds: int = _env_int("SEARCH_CHUNK_SECONDS", 14)
    search_chunk_max_chars: int = _env_int("SEARCH_CHUNK_MAX_CHARS", 320)

    manual_chunk_seconds: int = _env_int("MANUAL_CHUNK_SECONDS", 90)
    manual_llm_chunk_seconds: int = _env_int("MANUAL_LLM_CHUNK_SECONDS", 300)
    manual_llm_chunk_max_chars: int = _env_int("MANUAL_LLM_CHUNK_MAX_CHARS", 7000)
    manual_terminology_hints: str = os.getenv("MANUAL_TERMINOLOGY_HINTS", "").strip()
    manual_screenshot_offset_seconds: int = _env_int("MANUAL_SCREENSHOT_OFFSET_SECONDS", 2)
    manual_screenshot_min_gap_seconds: int = _env_int("MANUAL_SCREENSHOT_MIN_GAP_SECONDS", 45)
    manual_screenshot_max_count: int = _env_int("MANUAL_SCREENSHOT_MAX_COUNT", 0)
    manual_llm_screenshot_max_count: int = _env_int("MANUAL_LLM_SCREENSHOT_MAX_COUNT", 0)
    manual_screenshot_width: int = _env_int("MANUAL_SCREENSHOT_WIDTH", 1280)
    manual_quality_mode_default: str = os.getenv("MANUAL_QUALITY_MODE_DEFAULT", "fast").strip().lower()
    manual_quality_max_loops: int = _env_int("MANUAL_QUALITY_MAX_LOOPS", 1)
    manual_fast_max_images: int = _env_int("MANUAL_FAST_MAX_IMAGES", 8)
    manual_quality_max_images: int = _env_int("MANUAL_QUALITY_MAX_IMAGES", 16)
    manual_vision_model: str = os.getenv("MANUAL_VISION_MODEL", "HuggingFaceTB/SmolVLM-500M-Instruct").strip()
    manual_min_image_quality_score: float = _env_float("MANUAL_MIN_IMAGE_QUALITY_SCORE", 0.35)
    manual_min_review_score: float = _env_float("MANUAL_MIN_REVIEW_SCORE", 0.78)

    llm_provider: str = os.getenv("LLM_PROVIDER", "llama_cpp")
    llm_model: str = os.getenv("LLM_MODEL", "llama3.1:8b")
    llm_model_path: Optional[Path] = _env_path("LLM_MODEL_PATH")
    llm_n_gpu_layers: int = _default_llm_gpu_layers()
    llm_n_threads: int = _env_auto_int("LLM_N_THREADS", _default_model_threads())
    llm_n_threads_batch: int = _env_auto_int("LLM_N_THREADS_BATCH", _default_batch_threads())
    llm_n_batch: int = _env_auto_int("LLM_N_BATCH", _default_llm_batch())
    llm_n_ubatch: int = _env_int("LLM_N_UBATCH", 512)
    llm_max_tokens_answer: int = _env_int("LLM_MAX_TOKENS_ANSWER", 256)
    llm_max_tokens_section: int = _env_int("LLM_MAX_TOKENS_SECTION", 1000)
    llm_timeout_seconds: int = _env_int("LLM_TIMEOUT_SECONDS", 900)
    llm_temperature: float = _env_float("LLM_TEMPERATURE", 0.2)
    llm_num_ctx: int = _env_auto_int("LLM_NUM_CTX", _default_llm_context())

    cors_origins: Tuple[str, ...] = _env_origins(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000",
    )
    cors_origin_regex: Optional[str] = os.getenv(
        "CORS_ORIGIN_REGEX",
        r"^http://(localhost|127\.0\.0\.1):\d+$",
    )


settings = Settings()
