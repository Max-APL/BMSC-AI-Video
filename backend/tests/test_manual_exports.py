from app.manual_exports import parse_markdown_blocks


def test_parse_markdown_blocks_identifies_document_structure():
    blocks = parse_markdown_blocks(
        "# Titulo\n\n"
        "## Seccion\n\n"
        "![Captura](screenshots/section-001.jpg)\n\n"
        "#### Procedimiento\n\n"
        "Parrafo uno\n"
        "continua.\n\n"
        "1. Paso uno\n"
        "- Nota\n"
    )

    assert blocks == [
        ("h1", "Titulo"),
        ("h2", "Seccion"),
        ("image", "Captura\nscreenshots/section-001.jpg"),
        ("h4", "Procedimiento"),
        ("paragraph", "Parrafo uno continua."),
        ("number", "Paso uno"),
        ("bullet", "Nota"),
    ]
