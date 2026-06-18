from app.manual_generation import build_extractive_manual, build_time_blocks, insert_section_screenshots
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

    assert "# Manual operativo: capacitacion" in result.content
    assert "## Procedimiento resumido" in result.content
    assert "## Desarrollo" in result.content
    assert "## Anexo: referencias de revision" in result.content
    assert "00:00:00.000" in result.content
    assert "[00:00:00.000 - 00:00:10.000]" not in result.content
    assert result.section_count == 1
    assert result.word_count > 20


def test_insert_section_screenshots_places_images_near_matching_steps():
    section = "\n".join(
        [
            "### Registro de celular",
            "",
            "#### Procedimiento",
            "1. Descargue o actualice la aplicacion BMSC Movil desde Play Store o App Store.",
            "2. Ingrese con su usuario y contrasena de banca por internet.",
            "3. Presione el boton para enviar el codigo al correo electronico registrado.",
            "4. Confirme el registro del celular.",
        ]
    )

    result = insert_section_screenshots(
        section,
        [
            (
                "screenshots/section-001-01.jpg",
                "Figura (00:01:31.000) - Presione el boton, enviar codigo a correo electronico.",
            )
        ],
    )

    lines = result.splitlines()
    image_index = lines.index(
        "![Figura (00:01:31.000) - Presione el boton, enviar codigo a correo electronico.](screenshots/section-001-01.jpg)"
    )
    assert lines[image_index - 4] == "3. Presione el boton para enviar el codigo al correo electronico registrado."
    assert lines[image_index - 2].startswith("*La siguiente figura")
    assert "Apoyo visual" not in lines[image_index - 2]
    assert "correo electronico" in lines[image_index - 2]


def test_insert_section_screenshots_uses_bullets_as_visual_anchors():
    section = "\n".join(
        [
            "### Registro de celular",
            "",
            "#### Procedimiento",
            "1. Descargue o actualice la aplicacion BMSC Movil desde Play Store o App Store.",
            "2. Ingrese con su usuario y contrasena de banca por internet.",
            "",
            "#### Metodos disponibles",
            "- Corre en pantalla el correo registrado en banca por internet.",
            "- Introduce la respuesta a la pregunta en el campo disponible.",
        ]
    )

    result = insert_section_screenshots(
        section,
        [
            (
                "screenshots/section-001-01.jpg",
                "Figura (00:01:25.000) - Opcion 1, corre en pantalla el correo registrado en banca por internet.",
            ),
            (
                "screenshots/section-001-02.jpg",
                "Figura (00:01:45.000) - Introduce la respuesta a la pregunta en el campo disponible para registrar este equipo.",
            ),
        ],
    )

    lines = result.splitlines()
    email_image_index = lines.index(
        "![Figura (00:01:25.000) - Opcion 1, corre en pantalla el correo registrado en banca por internet.](screenshots/section-001-01.jpg)"
    )
    question_image_index = lines.index(
        "![Figura (00:01:45.000) - Introduce la respuesta a la pregunta en el campo disponible para registrar este equipo.](screenshots/section-001-02.jpg)"
    )

    assert lines[email_image_index - 4] == "- Corre en pantalla el correo registrado en banca por internet."
    assert lines[email_image_index - 2].startswith("*La siguiente figura")
    assert "Apoyo visual" not in lines[email_image_index - 2]
    assert lines[question_image_index - 4] == "- Introduce la respuesta a la pregunta en el campo disponible."
    assert lines[question_image_index - 2].startswith("*La siguiente figura")
    assert "Apoyo visual" not in lines[question_image_index - 2]
