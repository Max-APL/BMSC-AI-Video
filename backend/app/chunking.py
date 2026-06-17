from __future__ import annotations

from typing import Iterable, List, Set, Tuple

from .models import SearchChunk, TranscriptSegment
from .timecodes import format_timecode


def build_search_chunks(
    segments: Iterable[TranscriptSegment],
    target_seconds: int,
    max_chars: int,
) -> List[SearchChunk]:
    chunks: List[SearchChunk] = []
    clean_segments = [segment for segment in segments if segment.text.strip()]
    seen: Set[Tuple[int, ...]] = set()

    def add_chunk(items: List[TranscriptSegment]) -> None:
        if not items:
            return
        segment_ids = tuple(segment.id for segment in items)
        if segment_ids in seen:
            return
        seen.add(segment_ids)
        start = items[0].start_seconds
        end = items[-1].end_seconds
        chunks.append(
            SearchChunk(
                id=len(chunks),
                segment_ids=list(segment_ids),
                start_seconds=start,
                end_seconds=end,
                start_timecode=format_timecode(start),
                end_timecode=format_timecode(end),
                text=" ".join(segment.text.strip() for segment in items).strip(),
            )
        )

    for start_index in range(len(clean_segments)):
        current: List[TranscriptSegment] = []
        current_chars = 0

        for segment in clean_segments[start_index:]:
            clean_text = segment.text.strip()
            candidate_duration = segment.end_seconds - clean_segments[start_index].start_seconds
            candidate_chars = current_chars + len(clean_text)
            if current and (candidate_duration > target_seconds or candidate_chars > max_chars):
                break

            current.append(segment)
            current_chars = candidate_chars
            add_chunk(current.copy())

    return chunks
