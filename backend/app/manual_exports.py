from __future__ import annotations

import html
import re
from pathlib import Path
from typing import List, Tuple


class ManualExportError(RuntimeError):
    pass


def export_manual(content: str, output_path: Path, output_format: str) -> Path:
    output_format = output_format.lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        output_path.write_text(content, encoding="utf-8")
        return output_path
    if output_format == "docx":
        return export_docx(content, output_path)
    if output_format == "pdf":
        return export_pdf(content, output_path)
    raise ManualExportError("Formato de descarga no soportado. Usa markdown, docx o pdf.")


def export_docx(content: str, output_path: Path) -> Path:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt
    except ImportError as exc:
        raise ManualExportError(
            "No se pudo generar DOCX porque falta python-docx. "
            "Instala dependencias con: pip install -r requirements.txt"
        ) from exc

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)

    styles = document.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(10.5)
    styles["Heading 1"].font.name = "Arial"
    styles["Heading 1"].font.size = Pt(18)
    styles["Heading 2"].font.name = "Arial"
    styles["Heading 2"].font.size = Pt(14)
    styles["Heading 3"].font.name = "Arial"
    styles["Heading 3"].font.size = Pt(12)

    for kind, text in parse_markdown_blocks(content):
        if kind == "h1":
            paragraph = document.add_heading(text, level=1)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "h2":
            document.add_heading(text, level=2)
        elif kind == "h3":
            document.add_heading(text, level=3)
        elif kind == "bullet":
            add_formatted_paragraph(document, text, style="List Bullet")
        elif kind == "number":
            add_formatted_paragraph(document, text, style="List Number")
        elif kind == "paragraph":
            add_formatted_paragraph(document, text)

    document.save(output_path)
    return output_path


def export_pdf(content: str, output_path: Path) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise ManualExportError(
            "No se pudo generar PDF porque falta reportlab. "
            "Instala dependencias con: pip install -r requirements.txt"
        ) from exc

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ManualTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#12395f"),
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualHeading2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#12395f"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualHeading3",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=colors.HexColor("#1f6ed4"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    body_style = ParagraphStyle(
        name="ManualBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=7,
    )
    bullet_style = ParagraphStyle(
        name="ManualBullet",
        parent=body_style,
        leftIndent=14,
    )

    story = []
    pending_bullets: List[ListItem] = []
    pending_numbers: List[ListItem] = []

    def flush_lists() -> None:
        nonlocal pending_bullets, pending_numbers
        if pending_bullets:
            story.append(ListFlowable(pending_bullets, bulletType="bullet", leftIndent=18))
            pending_bullets = []
            story.append(Spacer(1, 4))
        if pending_numbers:
            story.append(ListFlowable(pending_numbers, bulletType="1", leftIndent=18))
            pending_numbers = []
            story.append(Spacer(1, 4))

    for kind, text in parse_markdown_blocks(content):
        if kind not in {"bullet", "number"}:
            flush_lists()
        if kind == "h1":
            story.append(Paragraph(inline_markdown(text), styles["ManualTitle"]))
        elif kind == "h2":
            story.append(Paragraph(inline_markdown(text), styles["ManualHeading2"]))
        elif kind == "h3":
            story.append(Paragraph(inline_markdown(text), styles["ManualHeading3"]))
        elif kind == "bullet":
            pending_bullets.append(ListItem(Paragraph(inline_markdown(text), bullet_style)))
        elif kind == "number":
            pending_numbers.append(ListItem(Paragraph(inline_markdown(text), bullet_style)))
        elif kind == "paragraph":
            story.append(Paragraph(inline_markdown(text), body_style))
    flush_lists()

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Manual de capacitacion",
    )
    document.build(story)
    return output_path


def parse_markdown_blocks(content: str) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    paragraph_lines: List[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            blocks.append(("paragraph", " ".join(paragraph_lines).strip()))
            paragraph_lines = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue
        if line.startswith("# "):
            flush_paragraph()
            blocks.append(("h1", line[2:].strip()))
        elif line.startswith("## "):
            flush_paragraph()
            blocks.append(("h2", line[3:].strip()))
        elif line.startswith("### "):
            flush_paragraph()
            blocks.append(("h3", line[4:].strip()))
        elif line.startswith("- "):
            flush_paragraph()
            blocks.append(("bullet", line[2:].strip()))
        elif re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            blocks.append(("number", re.sub(r"^\d+\.\s+", "", line).strip()))
        else:
            paragraph_lines.append(line)
    flush_paragraph()
    return blocks


def add_formatted_paragraph(document, text: str, style: str | None = None) -> None:
    paragraph = document.add_paragraph(style=style)
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
