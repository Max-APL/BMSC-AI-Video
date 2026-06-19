from __future__ import annotations

import shutil
import subprocess
import time
import wave
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Dict, List, Optional, Tuple

from .config import Settings
from .debug import log_event
from .models import TranscriptSegment
from .timecodes import format_timecode


class TranscriptionError(RuntimeError):
    pass


def get_wav_duration(audio_path: Path) -> Optional[float]:
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate <= 0:
                return None
            return round(frames / float(rate), 3)
    except (OSError, EOFError, wave.Error):
        return None


def _imageio_ffmpeg_exe() -> Optional[str]:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def get_ffmpeg_status(ffmpeg_bin: str = "ffmpeg") -> Dict[str, Optional[str] | bool]:
    configured_path = Path(ffmpeg_bin).expanduser()
    if configured_path.is_file():
        ffmpeg_path = str(configured_path.resolve())
    else:
        ffmpeg_path = shutil.which(ffmpeg_bin)

    if not ffmpeg_path:
        ffmpeg_path = _imageio_ffmpeg_exe()

    if not ffmpeg_path:
        return {
            "available": False,
            "path": None,
            "version": None,
            "error": f"{ffmpeg_bin} no esta disponible para el proceso del backend.",
        }

    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return {
            "available": False,
            "path": ffmpeg_path,
            "version": None,
            "error": str(exc),
        }

    lines = (result.stdout or result.stderr or "").splitlines()
    first_line = lines[0].strip() if lines else "ffmpeg disponible"
    return {
        "available": True,
        "path": ffmpeg_path,
        "version": first_line,
        "error": None,
    }


def extract_audio(video_path: Path, audio_path: Path, ffmpeg_bin: str = "ffmpeg") -> None:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_status = get_ffmpeg_status(ffmpeg_bin)
    if not ffmpeg_status["available"]:
        raise TranscriptionError(str(ffmpeg_status["error"]))

    command = [
        str(ffmpeg_status["path"]),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(audio_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise TranscriptionError(
            "ffmpeg no esta instalado o no esta disponible en PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise TranscriptionError(f"ffmpeg no pudo extraer el audio: {detail}") from exc


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._lock = Lock()

    @property
    def model(self):
        if self._model is None:
            device = self.settings.whisper_device
            compute_type = self.settings.whisper_compute_type
            log_event(
                "Loading faster-whisper model "
                f"model={self.settings.whisper_model} "
                f"device={device} "
                f"compute_type={compute_type}"
            )
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise TranscriptionError(
                    "faster-whisper no esta instalado. Ejecuta pip install -r requirements.txt."
                ) from exc

            kwargs: dict = {"device": device, "compute_type": compute_type}
            if self.settings.whisper_model_dir:
                kwargs["download_root"] = str(self.settings.whisper_model_dir)

            try:
                self._model = WhisperModel(self.settings.whisper_model, **kwargs)
                log_event(f"Faster-whisper model loaded on {device}")
            except Exception as exc:
                if device != "cpu":
                    log_event(
                        f"GPU model load failed ({exc}); retrying on CPU with int8"
                    )
                    kwargs["device"] = "cpu"
                    kwargs["compute_type"] = "int8"
                    self._model = WhisperModel(self.settings.whisper_model, **kwargs)
                    log_event("Faster-whisper model loaded on CPU (fallback)")
                else:
                    raise TranscriptionError(f"No se pudo cargar faster-whisper: {exc}") from exc
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        on_segment: Optional[Callable[[TranscriptSegment], None]] = None,
        video_id: Optional[str] = None,
    ) -> Tuple[List[TranscriptSegment], Optional[str], Optional[float]]:
        log_event(f"Waiting for local Whisper lock. audio={audio_path}", video_id)
        with self._lock:
            log_event(f"Whisper lock acquired. audio_size={audio_path.stat().st_size} bytes", video_id)
            started_at = time.monotonic()
            stop_heartbeat = Event()
            progress_state = {"segments": 0, "last_timecode": "00:00:00.000"}

            def heartbeat() -> None:
                while not stop_heartbeat.wait(10):
                    elapsed = round(time.monotonic() - started_at, 1)
                    log_event(
                        "Whisper still running "
                        f"elapsed={elapsed}s "
                        f"segments={progress_state['segments']} "
                        f"last_timecode={progress_state['last_timecode']}",
                        video_id,
                    )

            heartbeat_thread = Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()

            log_event("Starting faster-whisper transcription call", video_id)
            model = self.model
            segments_iterator, info = model.transcribe(
                str(audio_path),
                language=self.settings.whisper_language,
                vad_filter=True,
                beam_size=5,
            )
            log_event("Faster-whisper returned segment iterator; consuming segments", video_id)

            segments: List[TranscriptSegment] = []
            try:
                for segment in segments_iterator:
                    text = " ".join(segment.text.strip().split())
                    if not text:
                        continue

                    start = round(float(segment.start), 3)
                    end = round(float(segment.end), 3)
                    segments.append(
                        TranscriptSegment(
                            id=len(segments),
                            start_seconds=start,
                            end_seconds=end,
                            start_timecode=format_timecode(start),
                            end_timecode=format_timecode(end),
                            text=text,
                        )
                    )
                    progress_state["segments"] = len(segments)
                    progress_state["last_timecode"] = segments[-1].end_timecode
                    log_event(
                        "Segment emitted "
                        f"id={segments[-1].id} "
                        f"start={segments[-1].start_timecode} "
                        f"end={segments[-1].end_timecode} "
                        f"text_chars={len(text)}",
                        video_id,
                    )
                    if on_segment:
                        on_segment(segments[-1])
            finally:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=1)

            language = getattr(info, "language", None)
            duration = getattr(info, "duration", None)
            elapsed = round(time.monotonic() - started_at, 1)
            log_event(
                "Whisper transcription finished "
                f"elapsed={elapsed}s segments={len(segments)} "
                f"language={language} duration={duration}",
                video_id,
            )
            return segments, language, duration
