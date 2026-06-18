from app.manual_generation import build_text_blocks
from app.models import TranscriptSegment
from app.screenshots import build_screenshot_targets
from app.timecodes import format_timecode


def make_segment(idx: int, start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        id=idx,
        start_seconds=start,
        end_seconds=end,
        start_timecode=format_timecode(start),
        end_timecode=format_timecode(end),
        text=text,
    )


def test_build_screenshot_targets_uses_actionable_segments_inside_single_llm_block():
    segments = [
        make_segment(0, 0, 5, "Bienvenido a la capacitacion."),
        make_segment(1, 20, 25, "Primero, descarga la aplicacion desde la tienda."),
        make_segment(2, 40, 45, "Ingresa utilizando tu usuario y contrasena."),
        make_segment(3, 60, 65, "Recuerda que el registro se realiza una sola vez."),
        make_segment(4, 80, 85, "Presiona el boton enviar codigo a correo electronico."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=10,
    )

    assert len(targets) == 3
    assert all(target.index == 1 for target in targets)
    assert targets[0].start_seconds == 20
    assert "Recuerda" not in " ".join(target.text for target in targets)
