from pathlib import Path

import pytest

from app.config import Settings
from app.models import ManualQualityMode
from app.screenshots import ManualScreenshot
from app.visual_analysis import analyze_manual_screenshots


PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw


def make_screenshot(path: Path, index: int) -> ManualScreenshot:
    return ManualScreenshot(
        block_index=1,
        path=path,
        relative_path=f"screenshots/test-{index}.jpg",
        timecode=f"00:00:0{index}.000",
        caption=f"Figura (00:00:0{index}.000) - Pantalla de prueba {index}.",
    )


def test_analyze_manual_screenshots_filters_duplicates(tmp_path):
    first = tmp_path / "first.jpg"
    duplicate = tmp_path / "duplicate.jpg"
    image = Image.new("RGB", (320, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 300, 160), outline="black", width=4)
    draw.text((40, 70), "Guardar cambios", fill="black")
    image.save(first)
    image.save(duplicate)

    settings = Settings(
        manual_fast_max_images=8,
        manual_min_image_quality_score=0.0,
    )

    kept, evidence = analyze_manual_screenshots(
        [make_screenshot(first, 1), make_screenshot(duplicate, 2)],
        settings=settings,
        quality_mode=ManualQualityMode.fast,
    )

    assert len(kept) == 1
    assert len(evidence) == 2
    assert any(item.quality.duplicate_of for item in evidence)
