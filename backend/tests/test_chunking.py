from app.chunking import build_search_chunks
from app.models import TranscriptSegment
from app.timecodes import format_timecode


def segment(idx: int, start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        id=idx,
        start_seconds=start,
        end_seconds=end,
        start_timecode=format_timecode(start),
        end_timecode=format_timecode(end),
        text=text,
    )


def test_build_search_chunks_keeps_short_answer_precise():
    segments = [
        segment(0, 2.19, 9.07, "Para ofrecerte seguridad en banca movil."),
        segment(1, 9.07, 12.91, "Registro de celular."),
        segment(2, 12.91, 19.31, "Esta funcionalidad reemplaza al token."),
        segment(3, 19.31, 26.19, "Te enviaremos la clave para aprobar transacciones."),
        segment(4, 26.19, 29.71, "Atento, te llevaremos paso a paso."),
        segment(
            5,
            29.87,
            38.35,
            "Primero, descarga o actualiza gratuitamente la aplicacion movil desde la tienda de aplicaciones.",
        ),
        segment(6, 38.35, 43.31, "Ingresa la aplicacion usando tu usuario y contrasena."),
    ]

    chunks = build_search_chunks(segments, target_seconds=14, max_chars=320)

    assert any(chunk.segment_ids == [5] for chunk in chunks)
    assert all(chunk.end_seconds - chunk.start_seconds <= 14 for chunk in chunks)
