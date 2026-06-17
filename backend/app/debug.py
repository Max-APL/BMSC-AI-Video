from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def log_event(message: str, video_id: Optional[str] = None) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prefix = f"[{timestamp}]"
    if video_id:
        prefix = f"{prefix} [video:{video_id}]"
    print(f"{prefix} {message}", flush=True)
