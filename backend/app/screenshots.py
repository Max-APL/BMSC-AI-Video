from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .manual_generation import ACTION_PATTERNS, TranscriptBlock, clean_transcript_text
from .models import TranscriptSegment
from .transcription import get_ffmpeg_status


class ScreenshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualScreenshot:
    block_index: int
    path: Path
    relative_path: str
    timecode: str
    caption: str


def extract_manual_screenshots(
    *,
    video_path: Path,
    output_dir: Path,
    blocks: List[TranscriptBlock],
    ffmpeg_bin: str,
    offset_seconds: int,
    width: int,
    max_count: int,
) -> List[ManualScreenshot]:
    ffmpeg_status = get_ffmpeg_status(ffmpeg_bin)
    if not ffmpeg_status["available"]:
        raise ScreenshotError(str(ffmpeg_status["error"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots: List[ManualScreenshot] = []
    selected_blocks = select_blocks(blocks, max_count)
    for image_index, block in enumerate(selected_blocks, start=1):
        filename = f"section-{block.index:03d}-{image_index:02d}.jpg"
        output_path = output_dir / filename
        timestamp = choose_timestamp(block, offset_seconds)
        command = [
            str(ffmpeg_status["path"]),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "3",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise ScreenshotError(f"ffmpeg no pudo extraer captura: {detail}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ScreenshotError("ffmpeg excedio el tiempo limite extrayendo capturas.") from exc

        if output_path.exists() and output_path.stat().st_size > 0:
            screenshots.append(
                ManualScreenshot(
                    block_index=block.index,
                    path=output_path,
                    relative_path=f"screenshots/{filename}",
                    timecode=seconds_to_timecode(timestamp),
                    caption=build_caption(block, seconds_to_timecode(timestamp)),
                )
            )
    return screenshots


def select_blocks(blocks: List[TranscriptBlock], max_count: int) -> List[TranscriptBlock]:
    if not blocks:
        return []
    if max_count <= 0:
        return blocks
    if len(blocks) <= max_count:
        return blocks
    if max_count == 1:
        return [blocks[len(blocks) // 2]]

    last_index = len(blocks) - 1
    selected_indexes = {
        round(position * last_index / (max_count - 1))
        for position in range(max_count)
    }
    return [blocks[index] for index in sorted(selected_indexes)]


def build_screenshot_targets(
    *,
    segments: Sequence[TranscriptSegment],
    parent_blocks: Sequence[TranscriptBlock],
    max_count: int,
    key_points_only: bool = False,
    min_gap_seconds: int = 45,
) -> List[TranscriptBlock]:
    if max_count < 0:
        return []

    scored_candidates = [
        (segment, score_visual_segment(segment.text))
        for segment in segments
        if segment.text.strip()
    ]
    minimum_score = 2 if key_points_only else 1
    candidates = [
        (segment, score)
        for segment, score in scored_candidates
        if score >= minimum_score
    ]
    if not candidates:
        candidates = [
            (segment, score)
            for segment, score in scored_candidates
            if score > 0
        ]
    if not candidates:
        candidates = [
            (segment, 0)
            for segment in segments
            if segment.text.strip()
        ]

    if key_points_only and parent_blocks:
        selected_segments = select_key_segments_by_block(
            scored_candidates,
            parent_blocks,
            max_count,
            minimum_score=minimum_score,
            min_gap_seconds=min_gap_seconds,
        )
        if not selected_segments:
            selected_segments = select_representative_segments_by_block(
                scored_candidates,
                parent_blocks,
                max_count,
                min_gap_seconds=min_gap_seconds,
            )
    else:
        selected_segments = select_key_segments(
            candidates,
            max_count,
            min_gap_seconds=min_gap_seconds,
        )
    return [
        segment_to_target(segment, parent_blocks)
        for segment in selected_segments
    ]


def score_visual_segment(text: str) -> int:
    normalized = clean_transcript_text(text).lower()
    if not normalized:
        return 0

    score = 0
    starts_with_action = any(normalized.startswith(pattern) for pattern in ACTION_PATTERNS)
    starts_with_visual_cue = normalized.startswith(
        (
            "vamos a ver",
            "veamos",
            "vemos",
            "aqui",
            "aquí",
            "aca",
            "acá",
            "en pantalla",
            "en esta pantalla",
            "en la pantalla",
            "desde la consola",
        )
    )
    if starts_with_action and not normalized.startswith(("recuerda", "debe")):
        score += 2
    if starts_with_visual_cue:
        score += 2
    if normalized.startswith(("aparecera", "aparecerá", "se mostrara", "se mostrará", "se enviara", "se enviará")):
        score += 2
    visual_terms = (
        "pantalla",
        "ventana",
        "consola",
        "menu",
        "menú",
        "pestana",
        "pestaña",
        "panel",
        "formulario",
        "tabla",
        "lista",
        "diagrama",
        "diapositiva",
        "slide",
        "presentacion",
        "presentación",
        "ruta",
        "directorio",
        "archivo",
        "configuracion",
        "configuración",
        "dominio",
        "servidor",
        "server",
        "cluster",
        "asistente",
        "wizard",
        "boton",
        "botón",
        "opcion",
        "opción",
        "campo",
        "codigo",
        "código",
        "aplicacion",
        "aplicación",
        "correo",
        "alias",
        "validacion",
        "validación",
        "mensaje",
        "usuario",
        "contrasena",
        "contraseña",
        "tienda",
        "play store",
        "app store",
        "token",
    )
    has_visual_term = any(term in normalized for term in visual_terms)
    if has_visual_term:
        score += 2
    if (starts_with_action or starts_with_visual_cue) and has_visual_term:
        score += 1
    return score


def select_key_segments(
    scored_segments: Sequence[tuple[TranscriptSegment, int]],
    max_count: int,
    *,
    min_gap_seconds: int,
) -> List[TranscriptSegment]:
    items = list(scored_segments)
    if max_count > 0 and len(items) <= max_count:
        return [segment for segment, _score in sorted(items, key=lambda item: item[0].start_seconds)]

    ranked = sorted(
        items,
        key=lambda item: (-item[1], item[0].start_seconds),
    )
    selected: List[TranscriptSegment] = []
    for segment, _score in ranked:
        if all(abs(segment.start_seconds - chosen.start_seconds) >= min_gap_seconds for chosen in selected):
            selected.append(segment)
        if max_count > 0 and len(selected) >= max_count:
            break

    if max_count > 0 and len(selected) < max_count:
        for segment, _score in ranked:
            if segment not in selected:
                selected.append(segment)
            if len(selected) >= max_count:
                break

    return sorted(selected, key=lambda segment: segment.start_seconds)


def select_key_segments_by_block(
    scored_segments: Sequence[tuple[TranscriptSegment, int]],
    parent_blocks: Sequence[TranscriptBlock],
    max_count: int,
    *,
    minimum_score: int,
    min_gap_seconds: int,
) -> List[TranscriptSegment]:
    if max_count < 0:
        return []

    items = [
        (segment, score, find_parent_block_index(segment, parent_blocks))
        for segment, score in scored_segments
        if segment.text.strip()
    ]
    if not items:
        return []

    strict_items = [
        item
        for item in items
        if item[1] >= minimum_score
    ]
    if not strict_items:
        return []

    selected: List[TranscriptSegment] = []
    selected_ids: set[int] = set()
    coverage_blocks = select_blocks(list(parent_blocks), max_count)
    for block in coverage_blocks:
        block_items = [
            item
            for item in strict_items
            if item[2] == block.index
        ]
        if not block_items:
            continue

        segment, _score, _block_index = sorted(
            block_items,
            key=lambda item: (-item[1], item[0].start_seconds),
        )[0]
        if segment.id not in selected_ids:
            selected.append(segment)
            selected_ids.add(segment.id)
        if max_count > 0 and len(selected) >= max_count:
            return sorted(selected, key=lambda segment: segment.start_seconds)

    ranked = sorted(
        strict_items,
        key=lambda item: (-item[1], item[0].start_seconds),
    )
    for segment, _score, _block_index in ranked:
        if segment.id in selected_ids:
            continue
        if any(abs(segment.start_seconds - chosen.start_seconds) < min_gap_seconds for chosen in selected):
            continue
        selected.append(segment)
        selected_ids.add(segment.id)
        if max_count > 0 and len(selected) >= max_count:
            break

    return sorted(selected, key=lambda segment: segment.start_seconds)


def select_representative_segments_by_block(
    scored_segments: Sequence[tuple[TranscriptSegment, int]],
    parent_blocks: Sequence[TranscriptBlock],
    max_count: int,
    *,
    min_gap_seconds: int,
) -> List[TranscriptSegment]:
    if max_count < 0:
        return []

    items = [
        (segment, score, find_parent_block_index(segment, parent_blocks))
        for segment, score in scored_segments
        if segment.text.strip()
    ]
    if not items:
        return []

    selected: List[TranscriptSegment] = []
    selected_ids: set[int] = set()
    coverage_blocks = select_blocks(list(parent_blocks), max_count)
    for block in coverage_blocks:
        block_items = [
            item
            for item in items
            if item[2] == block.index
        ]
        if not block_items:
            continue

        segment, _score, _block_index = sorted(
            block_items,
            key=representative_segment_sort_key,
        )[0]
        if segment.id in selected_ids:
            continue
        if any(abs(segment.start_seconds - chosen.start_seconds) < min_gap_seconds for chosen in selected):
            continue
        selected.append(segment)
        selected_ids.add(segment.id)
        if max_count > 0 and len(selected) >= max_count:
            break

    if max_count > 0 and len(selected) < max_count:
        ranked = sorted(items, key=representative_segment_sort_key)
        for segment, _score, _block_index in ranked:
            if segment.id in selected_ids:
                continue
            selected.append(segment)
            selected_ids.add(segment.id)
            if len(selected) >= max_count:
                break

    return sorted(selected, key=lambda segment: segment.start_seconds)


def representative_segment_sort_key(item: tuple[TranscriptSegment, int, int]) -> tuple[int, int, float]:
    segment, score, _block_index = item
    normalized = clean_transcript_text(segment.text).lower()
    action_bonus = 1 if any(normalized.startswith(pattern) for pattern in ACTION_PATTERNS) else 0
    return (-score, -action_bonus, segment.start_seconds)


def select_segments(segments: Sequence[TranscriptSegment], max_count: int) -> List[TranscriptSegment]:
    items = list(segments)
    if len(items) <= max_count:
        return items
    if max_count == 1:
        return [items[len(items) // 2]]

    last_index = len(items) - 1
    selected_indexes = {
        round(position * last_index / (max_count - 1))
        for position in range(max_count)
    }
    return [items[index] for index in sorted(selected_indexes)]


def segment_to_target(
    segment: TranscriptSegment,
    parent_blocks: Sequence[TranscriptBlock],
) -> TranscriptBlock:
    parent_index = find_parent_block_index(segment, parent_blocks)
    return TranscriptBlock(
        index=parent_index,
        start_seconds=segment.start_seconds,
        end_seconds=segment.end_seconds,
        start_timecode=segment.start_timecode,
        end_timecode=segment.end_timecode,
        text=f"[{segment.start_timecode} - {segment.end_timecode}] {segment.text.strip()}",
        segment_count=1,
    )


def find_parent_block_index(
    segment: TranscriptSegment,
    parent_blocks: Sequence[TranscriptBlock],
) -> int:
    if not parent_blocks:
        return 1
    midpoint = segment.start_seconds + ((segment.end_seconds - segment.start_seconds) / 2)
    for block in parent_blocks:
        if block.start_seconds <= midpoint <= block.end_seconds:
            return block.index
    return parent_blocks[-1].index


def choose_timestamp(block: TranscriptBlock, offset_seconds: int) -> float:
    start = block.start_seconds
    end = block.end_seconds
    if end <= start:
        return max(0.0, start)
    target = start + max(0, offset_seconds)
    if target >= end:
        target = start + ((end - start) / 2)
    return max(0.0, target)


def build_caption(block: TranscriptBlock, timecode: str) -> str:
    text = clean_transcript_text(block.text)
    if len(text) > 120:
        text = text[:117].rstrip() + "..."
    return f"Figura ({timecode}) - {text}"


def seconds_to_timecode(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"
