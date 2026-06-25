from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .config import Settings
from .hf_models import get_vision_analyzer
from .models import ManualQualityMode
from .screenshots import ManualScreenshot


@dataclass(frozen=True)
class ImageQuality:
    sharpness: float
    brightness: float
    contrast: float
    score: float
    duplicate_of: Optional[str] = None
    visual_description: Optional[str] = None
    kept: bool = True
    reason: Optional[str] = None


@dataclass(frozen=True)
class VisualEvidence:
    path: str
    block_index: int
    timecode: str
    caption: str
    quality: ImageQuality

    def to_dict(self) -> dict:
        payload = asdict(self)
        return payload


def analyze_manual_screenshots(
    screenshots: Iterable[ManualScreenshot],
    *,
    settings: Settings,
    quality_mode: ManualQualityMode,
) -> Tuple[List[ManualScreenshot], List[VisualEvidence]]:
    items = list(screenshots)
    if not items:
        return [], []

    max_images = (
        settings.manual_quality_max_images
        if quality_mode == ManualQualityMode.quality
        else settings.manual_fast_max_images
    )
    if max_images > 0:
        items = items[:max_images]

    signatures: dict[str, List[float]] = {}
    evidence: List[VisualEvidence] = []
    kept: List[ManualScreenshot] = []

    for screenshot in items:
        quality = score_image(screenshot.path)
        duplicate_of = find_duplicate(quality_signature(screenshot.path), signatures)
        visual_description = None
        keep = quality.score >= settings.manual_min_image_quality_score
        reason = None

        if duplicate_of:
            keep = False
            reason = f"duplicada de {duplicate_of}"
        elif not keep:
            reason = "baja calidad visual"

        if keep and quality_mode == ManualQualityMode.quality:
            visual_description = get_vision_analyzer(settings).describe_image(screenshot.path)
            if not is_vlm_description_useful(visual_description):
                keep = False
                reason = "modelo visual devolvio descripcion inútil o sin aporte"

        final_quality = ImageQuality(
            sharpness=quality.sharpness,
            brightness=quality.brightness,
            contrast=quality.contrast,
            score=quality.score,
            duplicate_of=duplicate_of,
            visual_description=visual_description,
            kept=keep,
            reason=reason,
        )
        evidence.append(
            VisualEvidence(
                path=screenshot.relative_path,
                block_index=screenshot.block_index,
                timecode=screenshot.timecode,
                caption=screenshot.caption,
                quality=final_quality,
            )
        )

        signature = quality_signature(screenshot.path)
        if signature:
            signatures[screenshot.relative_path] = signature
        if keep:
            kept.append(replace(screenshot, caption=enhance_caption(screenshot.caption, final_quality)))

    if not kept and items:
        best = max(items, key=lambda item: score_image(item.path).score)
        kept = [best]
        evidence.append(
            VisualEvidence(
                path=best.relative_path,
                block_index=best.block_index,
                timecode=best.timecode,
                caption=best.caption,
                quality=ImageQuality(
                    **{
                        **asdict(score_image(best.path)),
                        "kept": True,
                        "reason": "conservada como mejor captura disponible",
                    }
                ),
            )
        )

    return kept, evidence


def score_image(path: Path) -> ImageQuality:
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError:
        return ImageQuality(sharpness=0.7, brightness=0.7, contrast=0.7, score=0.7)

    try:
        image = Image.open(path).convert("L").resize((160, 90))
        stat = ImageStat.Stat(image)
        brightness = clamp(stat.mean[0] / 255.0)
        contrast = clamp(stat.stddev[0] / 80.0)
        edges = image.filter(ImageFilter.FIND_EDGES)
        sharpness = clamp(ImageStat.Stat(edges).mean[0] / 35.0)
        exposure = 1.0 - min(abs(brightness - 0.52) / 0.52, 1.0)
        score = clamp((sharpness * 0.45) + (contrast * 0.35) + (exposure * 0.20))
        return ImageQuality(
            sharpness=round(sharpness, 4),
            brightness=round(brightness, 4),
            contrast=round(contrast, 4),
            score=round(score, 4),
        )
    except Exception:
        return ImageQuality(sharpness=0.5, brightness=0.5, contrast=0.5, score=0.5)


def quality_signature(path: Path) -> List[float]:
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        image = Image.open(path).convert("L").resize((8, 8))
        pixels = list(image.getdata())
        average = sum(pixels) / max(1, len(pixels))
        return [1.0 if pixel >= average else 0.0 for pixel in pixels]
    except Exception:
        return []


def find_duplicate(signature: List[float], seen: dict[str, List[float]]) -> Optional[str]:
    if not signature:
        return None
    for path, other in seen.items():
        if not other or len(other) != len(signature):
            continue
        distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(signature, other)))
        if distance <= 2.0:
            return path
    return None


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def is_vlm_description_useful(visual_description: Optional[str]) -> bool:
    if not visual_description:
        return False
    desc_upper = visual_description.strip().upper()
    gibberish_patterns = [
        "SIN_APORTE",
        "NO SE PUEDE UTILIZAR",
        "NO DATA AVAILABLE",
        "CARRO Y UN PISO",
        "OPORTUNIDAD DE APORTE",
        "OPORTUNA PARA UNA OPORTUNA",
        "CAPTURA DE LA IMAGEM",
        "PUNTUACIÓN QUE SE HA UTILIZADO",
    ]
    for pattern in gibberish_patterns:
        if pattern in desc_upper:
            return False
    return True


def enhance_caption(caption: str, quality: ImageQuality) -> str:
    """
    Preserves the original transcript-based caption instead of destructively
    replacing it with VLM gibberish.
    """
    return caption
