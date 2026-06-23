from __future__ import annotations

import shutil
import subprocess
import time
import uuid
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


def build_audio_chunk_ranges(
    duration_seconds: float,
    chunk_seconds: int,
) -> List[Tuple[int, float, float]]:
    if duration_seconds <= 0 or chunk_seconds <= 0:
        return []

    ranges: List[Tuple[int, float, float]] = []
    chunk_size = float(chunk_seconds)
    start = 0.0
    index = 0
    while start < duration_seconds:
        length = min(chunk_size, duration_seconds - start)
        if length <= 0:
            break
        ranges.append((index, round(start, 3), round(length, 3)))
        index += 1
        start = index * chunk_size
    return ranges


def extract_audio_chunk(
    audio_path: Path,
    chunk_path: Path,
    start_seconds: float,
    duration_seconds: float,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_status = get_ffmpeg_status(ffmpeg_bin)
    if not ffmpeg_status["available"]:
        raise TranscriptionError(str(ffmpeg_status["error"]))

    command = [
        str(ffmpeg_status["path"]),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(audio_path),
        "-t",
        f"{duration_seconds:.3f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(chunk_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise TranscriptionError(
            "ffmpeg no esta instalado o no esta disponible en PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise TranscriptionError(f"ffmpeg no pudo crear el chunk de audio: {detail}") from exc


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

            segments: List[TranscriptSegment] = []
            try:
                model = self.model
                audio_duration = get_wav_duration(audio_path)
                chunk_seconds = self.settings.whisper_audio_chunk_seconds
                if audio_duration and chunk_seconds > 0 and audio_duration > chunk_seconds:
                    language, duration = self._transcribe_chunked_wav(
                        model=model,
                        audio_path=audio_path,
                        duration_seconds=audio_duration,
                        chunk_seconds=chunk_seconds,
                        segments=segments,
                        progress_state=progress_state,
                        on_segment=on_segment,
                        video_id=video_id,
                    )
                else:
                    if chunk_seconds > 0 and audio_duration is None:
                        log_event(
                            "Whisper audio chunking skipped because duration is unknown",
                            video_id,
                        )
                    info = self._transcribe_file(
                        model=model,
                        audio_path=audio_path,
                        offset_seconds=0.0,
                        segments=segments,
                        progress_state=progress_state,
                        on_segment=on_segment,
                        video_id=video_id,
                    )
                    language = getattr(info, "language", None)
                    duration = getattr(info, "duration", audio_duration)
            finally:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=1)

            elapsed = round(time.monotonic() - started_at, 1)
            log_event(
                "Whisper transcription finished "
                f"elapsed={elapsed}s segments={len(segments)} "
                f"language={language} duration={duration}",
                video_id,
            )
            return segments, language, duration

    def _transcribe_chunked_wav(
        self,
        model,
        audio_path: Path,
        duration_seconds: float,
        chunk_seconds: int,
        segments: List[TranscriptSegment],
        progress_state: Dict[str, object],
        on_segment: Optional[Callable[[TranscriptSegment], None]],
        video_id: Optional[str],
    ) -> Tuple[Optional[str], float]:
        ranges = build_audio_chunk_ranges(duration_seconds, chunk_seconds)
        chunk_dir = audio_path.parent / f".whisper_chunks_{uuid.uuid4().hex}"
        language: Optional[str] = None

        log_event(
            "Whisper file chunking enabled "
            f"duration={duration_seconds}s "
            f"chunk_seconds={chunk_seconds} "
            f"chunks={len(ranges)}",
            video_id,
        )

        try:
            for chunk_index, start_seconds, length_seconds in ranges:
                chunk_path = chunk_dir / f"chunk_{chunk_index:05d}.wav"
                log_event(
                    "Preparing Whisper audio chunk "
                    f"index={chunk_index + 1}/{len(ranges)} "
                    f"start={format_timecode(start_seconds)} "
                    f"duration={length_seconds}s",
                    video_id,
                )
                extract_audio_chunk(
                    audio_path=audio_path,
                    chunk_path=chunk_path,
                    start_seconds=start_seconds,
                    duration_seconds=length_seconds,
                    ffmpeg_bin=self.settings.ffmpeg_bin,
                )
                info = self._transcribe_file(
                    model=model,
                    audio_path=chunk_path,
                    offset_seconds=start_seconds,
                    segments=segments,
                    progress_state=progress_state,
                    on_segment=on_segment,
                    video_id=video_id,
                )
                if language is None:
                    language = getattr(info, "language", None)

                completed_seconds = min(duration_seconds, start_seconds + length_seconds)
                progress_state["last_timecode"] = format_timecode(completed_seconds)
                try:
                    chunk_path.unlink()
                except OSError:
                    pass
        finally:
            shutil.rmtree(chunk_dir, ignore_errors=True)

        return language, duration_seconds

    def _transcribe_file(
        self,
        model,
        audio_path: Path,
        offset_seconds: float,
        segments: List[TranscriptSegment],
        progress_state: Dict[str, object],
        on_segment: Optional[Callable[[TranscriptSegment], None]],
        video_id: Optional[str],
    ):
        log_event(
            "Starting faster-whisper transcription call "
            f"audio={audio_path} "
            f"offset={format_timecode(offset_seconds)} "
            f"beam_size={self.settings.whisper_beam_size}",
            video_id,
        )
        segments_iterator, info = model.transcribe(
            str(audio_path),
            language=self.settings.whisper_language,
            vad_filter=True,
            beam_size=self.settings.whisper_beam_size,
        )
        log_event("Faster-whisper returned segment iterator; consuming segments", video_id)

        for segment in segments_iterator:
            text = " ".join(segment.text.strip().split())
            if not text:
                continue

            start = round(offset_seconds + float(segment.start), 3)
            end = round(offset_seconds + float(segment.end), 3)
            transcript_segment = TranscriptSegment(
                id=len(segments),
                start_seconds=start,
                end_seconds=end,
                start_timecode=format_timecode(start),
                end_timecode=format_timecode(end),
                text=text,
            )
            segments.append(transcript_segment)
            progress_state["segments"] = len(segments)
            progress_state["last_timecode"] = transcript_segment.end_timecode
            log_event(
                "Segment emitted "
                f"id={transcript_segment.id} "
                f"start={transcript_segment.start_timecode} "
                f"end={transcript_segment.end_timecode} "
                f"text_chars={len(text)}",
                video_id,
            )
            if on_segment:
                on_segment(transcript_segment)

        return info
