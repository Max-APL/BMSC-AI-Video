from __future__ import annotations

import re
from typing import List

from .models import TranscriptSegment

# Basic mapping for common ASR phonetic errors or domain-specific terminology.
# Keys are regex patterns or exact lowercased strings.
DEFAULT_TERMINOLOGY_MAP = {
    r"\bmsc m[oó]vil\b": "BMSC Móvil",
    r"\ba vestor\b": "App Store",
    r"\bplay store\b": "Play Store",
    r"\btoquen\b": "token",
    r"\bdebe sin producir\b": "debes introducir",
    r"\bdebe si producir\b": "debes introducir",
    r"\bbot[oó]n general\b": "botón Generar",
    r"\bdelegar[aá]\b": "llegará",
    r"\buna descompletada\b": "una vez completada",
    r"\bf[aá]ciletarte\b": "facilitarte",
    r"\bcorre en pantalla el correo\b": "corrobora en pantalla el correo",
}


def normalize_transcript_segments(
    segments: List[TranscriptSegment], terminology_hints: str = ""
) -> List[TranscriptSegment]:
    """
    Applies terminology normalization to transcript segments.
    """
    if not segments:
        return segments

    # Build the active map, allowing hints to override defaults
    active_map = dict(DEFAULT_TERMINOLOGY_MAP)

    if terminology_hints:
        # Simple CSV parser for hints like "MSC móvil=BMSC Móvil,toquen=token"
        hints = [h.strip() for h in terminology_hints.split(",")]
        for hint in hints:
            if "=" in hint:
                bad, good = hint.split("=", 1)
                bad = bad.strip().lower()
                good = good.strip()
                if bad and good:
                    # Escape the bad string to form a safe word-boundary regex
                    safe_bad = re.escape(bad)
                    pattern = rf"\b{safe_bad}\b"
                    active_map[pattern] = good

    # Apply normalizations
    normalized_segments = []
    for segment in segments:
        new_text = segment.text
        for pattern, replacement in active_map.items():
            # Use re.IGNORECASE to match regardless of original casing
            # Need a function to preserve case if it's purely capitalized? 
            # For now a direct replacement is fine as these are specific domain terms.
            new_text = re.sub(pattern, replacement, new_text, flags=re.IGNORECASE)

        normalized_segments.append(
            TranscriptSegment(
                id=segment.id,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                start_timecode=segment.start_timecode,
                end_timecode=segment.end_timecode,
                text=new_text,
            )
        )

    return normalized_segments
