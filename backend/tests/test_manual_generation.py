from app.manual_generation import build_extractive_manual, build_time_blocks
from app.models import TranscriptSegment, VideoMetadata, VideoStatus
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


def test_build_time_blocks_groups_segments_by_duration():
    segments = [
        make_segment(0, 0, 20, "Primero ingresa a la aplicacion."),
        make_segment(1, 20, 40, "Luego selecciona la opcion principal."),
        make_segment(2, 80, 110, "Finalmente confirma la operacion."),
    ]

    blocks = build_time_blocks(segments, chunk_seconds=60)

    assert len(blocks) == 2
    assert blocks[0].start_timecode == "00:00:00.000"
    assert blocks[1].start_timecode == "00:01:20.000"


def test_build_extractive_manual_includes_actions_and_references():
    metadata = VideoMetadata(
        id="video-1",
        original_filename="capacitacion.mp4",
        stored_filename="source.mp4",
        status=VideoStatus.ready,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        duration_seconds=60,
    )
    segments = [
        make_segment(0, 0, 10, "Primero ingresa con tu usuario."),
        make_segment(1, 10, 20, "Luego selecciona la opcion de registro."),
    ]

    result = build_extractive_manual(
        metadata,
        segments,
        chunk_seconds=300,
        include_timestamps=True,
    )

    assert "# Manual de capacitacion: capacitacion" in result.content
    assert "## Procedimiento resumido" in result.content
    assert "## Desarrollo" in result.content
    assert "## Anexo: referencias de revision" in result.content
    assert "00:00:00.000" in result.content
    assert "[00:00:00.000 - 00:00:10.000]" not in result.content
    assert result.section_count == 1
    assert result.word_count > 20
