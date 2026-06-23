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


def test_build_screenshot_targets_distributes_images_across_llm_blocks():
    segments = [
        make_segment(0, 0, 10, "Primero ingresa al modulo inicial."),
        make_segment(1, 40, 50, "Presiona el boton guardar en la pantalla inicial."),
        make_segment(2, 330, 340, "Selecciona la opcion de aprobacion en la pantalla."),
        make_segment(3, 370, 380, "Introduce el codigo en el campo disponible."),
        make_segment(4, 650, 660, "Finalmente aparecerá el mensaje de confirmacion."),
        make_segment(5, 690, 700, "Presiona el boton finalizar el proceso."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=3,
        key_points_only=True,
    )

    assert [target.index for target in targets] == [1, 2, 3]
    assert [target.start_seconds for target in targets] == [40, 330, 650]


def test_build_screenshot_targets_spreads_limited_count_over_long_video():
    segments = [
        make_segment(0, 10, 20, "Presiona el boton de inicio en pantalla."),
        make_segment(1, 310, 320, "Presiona el boton continuar en pantalla."),
        make_segment(2, 610, 620, "Presiona el boton aprobar en pantalla."),
        make_segment(3, 910, 920, "Presiona el boton finalizar en pantalla."),
        make_segment(4, 1210, 1220, "Presiona el boton confirmar en pantalla."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=3,
        key_points_only=True,
    )

    assert [target.index for target in targets] == [1, 3, 5]
    assert [target.start_seconds for target in targets] == [10, 610, 1210]


def test_build_screenshot_targets_auto_skips_blocks_without_visual_content():
    segments = [
        make_segment(0, 10, 20, "Presiona el boton de inicio en pantalla."),
        make_segment(1, 310, 320, "En esta parte se explica el contexto general de la arquitectura."),
        make_segment(2, 610, 620, "Selecciona la opcion de configuracion en pantalla."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=0,
        key_points_only=True,
    )

    assert [target.index for target in targets] == [1, 3]
    assert [target.start_seconds for target in targets] == [10, 610]


def test_build_screenshot_targets_auto_allows_multiple_content_points_in_one_block():
    segments = [
        make_segment(0, 20, 25, "Presiona el boton crear en pantalla."),
        make_segment(1, 35, 40, "Se explica el resultado de la accion anterior."),
        make_segment(2, 95, 100, "Introduce el codigo en el campo de validacion."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=0,
        key_points_only=True,
        min_gap_seconds=45,
    )

    assert [target.index for target in targets] == [1, 1]
    assert [target.start_seconds for target in targets] == [20, 95]


def test_build_screenshot_targets_detects_generic_training_visual_cues():
    segments = [
        make_segment(0, 10, 20, "Vamos a ver esta pantalla de configuracion general."),
        make_segment(1, 40, 50, "Este concepto se explica como referencia teorica."),
        make_segment(2, 90, 100, "Aqui se muestra la ruta del archivo en la consola."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=0,
        key_points_only=True,
        min_gap_seconds=45,
    )

    assert [target.start_seconds for target in targets] == [10, 90]


def test_build_screenshot_targets_falls_back_to_representative_blocks_when_visual_cues_are_missing():
    segments = [
        make_segment(0, 10, 20, "La arquitectura del servicio se compone de una capa de acceso."),
        make_segment(1, 70, 80, "La comunicacion interna mantiene una separacion por componentes."),
        make_segment(2, 330, 340, "El segundo modulo concentra las reglas de negocio."),
        make_segment(3, 390, 400, "La operacion finaliza con la revision del resultado."),
    ]
    blocks = build_text_blocks(segments, chunk_seconds=300, max_chars=7000)

    targets = build_screenshot_targets(
        segments=segments,
        parent_blocks=blocks,
        max_count=0,
        key_points_only=True,
        min_gap_seconds=45,
    )

    assert [target.index for target in targets] == [1, 2]
    assert [target.start_seconds for target in targets] == [10, 330]
