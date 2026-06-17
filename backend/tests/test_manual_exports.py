from app.manual_exports import parse_markdown_blocks


def test_parse_markdown_blocks_identifies_document_structure():
    blocks = parse_markdown_blocks(
        "# Titulo\n\n"
        "## Seccion\n\n"
        "Parrafo uno\n"
        "continua.\n\n"
        "1. Paso uno\n"
        "- Nota\n"
    )

    assert blocks == [
        ("h1", "Titulo"),
        ("h2", "Seccion"),
        ("paragraph", "Parrafo uno continua."),
        ("number", "Paso uno"),
        ("bullet", "Nota"),
    ]
