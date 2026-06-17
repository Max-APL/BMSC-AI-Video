from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .config import Settings
from .models import TranscriptSegment, VideoMetadata


@dataclass(frozen=True)
class ManualBuildResult:
    content: str
    section_count: int
    word_count: int


@dataclass(frozen=True)
class TranscriptBlock:
    index: int
    start_timecode: str
    end_timecode: str
    text: str
    segment_count: int


ACTION_PATTERNS = (
    "primero",
    "segundo",
    "tercero",
    "luego",
    "despues",
    "después",
    "finalmente",
    "ingresa",
    "selecciona",
    "presiona",
    "haz clic",
    "registra",
    "descarga",
    "actualiza",
    "debe",
    "recuerda",
    "verifica",
    "confirma",
)


def build_extractive_manual(
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    *,
    chunk_seconds: int,
    include_timestamps: bool,
) -> ManualBuildResult:
    blocks = build_time_blocks(segments, chunk_seconds=chunk_seconds)
    title = manual_title(metadata)
    full_text = clean_transcript_text("\n".join(block.text for block in blocks))
    actions = _detect_actions(full_text, limit=14)
    notes = detect_notes(full_text)
    lines = [
        f"# {title}",
        "",
        "## Proposito del manual",
        "",
        (
            "Este documento convierte el contenido de la capacitacion en una guia "
            "de consulta. Su objetivo es presentar el procedimiento explicado de "
            "forma ordenada, con lenguaje operativo y facil de seguir."
        ),
        "",
        "## Informacion del material",
        "",
        f"- Material de origen: {metadata.original_filename}",
        f"- Duracion aproximada: {format_duration(metadata.duration_seconds)}",
        "- Metodo de generacion: manual extractivo sin LLM",
        "",
        "## Como usar este manual",
        "",
        "1. Revise primero el procedimiento resumido.",
        "2. Consulte el desarrollo para entender el detalle de cada etapa.",
        "3. Use el anexo de referencias solo si necesita validar el punto exacto en el video.",
        "",
        "## Procedimiento resumido",
        "",
    ]

    if actions:
        for action_index, action in enumerate(actions, start=1):
            lines.append(f"{action_index}. {sentence_to_instruction(action)}")
    else:
        lines.append(
            "1. Revise el desarrollo del contenido y ejecute las acciones en el orden "
            "en que se presentan."
        )

    lines.extend(["", "## Desarrollo", ""])

    for block in blocks:
        section_text = clean_transcript_text(block.text)
        summary = summarize_block_text(section_text)
        lines.extend(
            [
                f"### Etapa {block.index}",
                "",
                summary,
                "",
            ]
        )

    if notes:
        lines.extend(["## Puntos de control", ""])
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.extend(
        [
            "## Cierre",
            "",
            (
                "Al completar los pasos descritos, el usuario deberia poder aplicar "
                "el procedimiento explicado en la capacitacion de forma consistente. "
                "Si algun paso no coincide con la aplicacion o sistema real, revise "
                "la capacitacion original o la documentacion interna vigente."
            ),
            "",
        ]
    )

    if include_timestamps:
        lines.extend(["## Anexo: referencias de revision", ""])
        for block in blocks:
            lines.append(f"- Etapa {block.index}: revisar en el video desde {block.start_timecode} hasta {block.end_timecode}.")
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    return ManualBuildResult(
        content=content,
        section_count=len(blocks),
        word_count=count_words(content),
    )


def build_llm_manual(
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    *,
    settings: Settings,
    provider: str,
    model: str,
    include_timestamps: bool,
    on_progress: Optional[Callable[[str, int, int, str], None]] = None,
) -> ManualBuildResult:
    if provider != "ollama":
        raise ValueError("Proveedor LLM no soportado. Usa provider='ollama'.")

    blocks = build_text_blocks(
        segments,
        chunk_seconds=settings.manual_chunk_seconds,
        max_chars=settings.manual_llm_chunk_max_chars,
    )
    client = OllamaClient(
        base_url=settings.llm_base_url,
        model=model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
    )
    title = manual_title(metadata)
    lines = [
        f"# {title}",
        "",
        "## Informacion del video",
        "",
        f"- Archivo: {metadata.original_filename}",
        f"- Duracion: {format_duration(metadata.duration_seconds)}",
        f"- Modo de generacion: LLM local via {provider}",
        f"- Modelo: {model}",
        "",
        "## Objetivo",
        "",
        (
            "Este manual fue redactado a partir de la transcripcion local del video. "
            "Las referencias temporales se conservan solo como apoyo de revision, no "
            "como reemplazo del procedimiento."
        ),
        "",
        "## Desarrollo",
        "",
    ]

    if on_progress:
        on_progress("\n".join(lines).strip() + "\n", 0, len(blocks), "")

    for block in blocks:
        prefix = "\n".join(lines).strip() + "\n\n"

        def handle_delta(partial_section: str, delta: str) -> None:
            if on_progress:
                on_progress(prefix + clean_markdown(partial_section), block.index, len(blocks), delta)

        generated = client.generate_section(
            title=title,
            block=block,
            include_timestamps=include_timestamps,
            on_delta=handle_delta,
        )
        lines.append(clean_markdown(generated))
        lines.append("")
        if on_progress:
            on_progress("\n".join(lines).strip() + "\n", block.index, len(blocks), "")

    lines.extend(
        [
            "## Referencias de revision",
            "",
        ]
    )
    for block in blocks:
        lines.append(f"- Bloque {block.index}: {block.start_timecode} - {block.end_timecode}")

    content = "\n".join(lines).strip() + "\n"
    if on_progress:
        on_progress(content, len(blocks), len(blocks), "")
    return ManualBuildResult(
        content=content,
        section_count=len(blocks),
        word_count=count_words(content),
    )


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: int,
        temperature: float,
        num_ctx: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.num_ctx = num_ctx

    def generate_section(
        self,
        *,
        title: str,
        block: TranscriptBlock,
        include_timestamps: bool,
        on_delta: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        timestamp_instruction = (
            "No insertes timestamps dentro del texto principal. Si necesitas conservar trazabilidad, agrega una linea final breve llamada 'Referencia de revision' con el rango del bloque."
            if include_timestamps
            else "No incluyas timestamps."
        )
        system_prompt = (
            "Eres un redactor tecnico experto en crear manuales de capacitacion. "
            "Trabajas solo con la transcripcion proporcionada. No inventes datos, "
            "no agregues requisitos no mencionados y no uses informacion externa. "
            "Responde exclusivamente en Markdown."
        )
        user_prompt = f"""
Genera una seccion profesional para un manual.

Manual: {title}
Bloque: {block.index}
Rango de video: {block.start_timecode} - {block.end_timecode}

Instrucciones:
- Escribe en espanol claro y formal.
- Usa un titulo de seccion especifico.
- Incluye una explicacion breve.
- Si hay procedimiento, conviertelo en pasos numerados.
- Agrega notas o advertencias solo si aparecen en la transcripcion.
- No escribas como transcripcion y no pegues dialogos.
- {timestamp_instruction}
- Mantente fiel a la transcripcion aunque tenga errores menores.

Transcripcion:
{block.text}
""".strip()
        return self.chat(system_prompt=system_prompt, user_prompt=user_prompt, on_delta=on_delta)

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        on_delta: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        payload = {
            "model": self.model,
            "stream": on_delta is not None,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if on_delta is None:
                    data = json.loads(response.read().decode("utf-8"))
                else:
                    parts: List[str] = []
                    for raw_line in response:
                        line = raw_line.decode("utf-8").strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        delta = data.get("message", {}).get("content") or ""
                        if delta:
                            parts.append(delta)
                            on_delta("".join(parts), delta)
                        if data.get("done"):
                            break
                    content = "".join(parts).strip()
                    if not content:
                        raise RuntimeError("Ollama no devolvio contenido para el manual.")
                    return content
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"No se pudo conectar con Ollama en {self.base_url}. "
                "Verifica que Ollama este corriendo y que el modelo este descargado."
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError("La generacion con Ollama excedio el tiempo limite.") from exc

        content = data.get("message", {}).get("content")
        if not content:
            raise RuntimeError("Ollama no devolvio contenido para el manual.")
        return content


def build_time_blocks(
    segments: List[TranscriptSegment],
    *,
    chunk_seconds: int,
) -> List[TranscriptBlock]:
    if not segments:
        return []

    blocks: List[TranscriptBlock] = []
    current: List[TranscriptSegment] = []
    current_start = segments[0].start_seconds

    for segment in segments:
        if current and segment.end_seconds - current_start > chunk_seconds:
            blocks.append(make_block(len(blocks) + 1, current))
            current = []
            current_start = segment.start_seconds
        current.append(segment)

    if current:
        blocks.append(make_block(len(blocks) + 1, current))
    return blocks


def build_text_blocks(
    segments: List[TranscriptSegment],
    *,
    chunk_seconds: int,
    max_chars: int,
) -> List[TranscriptBlock]:
    time_blocks = build_time_blocks(segments, chunk_seconds=chunk_seconds)
    blocks: List[TranscriptBlock] = []
    for block in time_blocks:
        if len(block.text) <= max_chars:
            blocks.append(TranscriptBlock(len(blocks) + 1, block.start_timecode, block.end_timecode, block.text, block.segment_count))
            continue

        lines = block.text.splitlines()
        current_lines: List[str] = []
        current_start = block.start_timecode
        current_end = block.end_timecode
        segment_count = 0
        for line in lines:
            if current_lines and sum(len(item) for item in current_lines) + len(line) > max_chars:
                blocks.append(
                    TranscriptBlock(
                        index=len(blocks) + 1,
                        start_timecode=current_start,
                        end_timecode=current_end,
                        text="\n".join(current_lines),
                        segment_count=segment_count,
                    )
                )
                current_lines = []
                current_start = extract_start_timecode(line) or current_end
                segment_count = 0
            current_lines.append(line)
            current_end = extract_end_timecode(line) or current_end
            segment_count += 1
        if current_lines:
            blocks.append(
                TranscriptBlock(
                    index=len(blocks) + 1,
                    start_timecode=current_start,
                    end_timecode=current_end,
                    text="\n".join(current_lines),
                    segment_count=segment_count,
                )
            )
    return blocks


def make_block(index: int, segments: Iterable[TranscriptSegment]) -> TranscriptBlock:
    items = list(segments)
    text_lines = [
        f"[{segment.start_timecode} - {segment.end_timecode}] {segment.text.strip()}"
        for segment in items
        if segment.text.strip()
    ]
    return TranscriptBlock(
        index=index,
        start_timecode=items[0].start_timecode,
        end_timecode=items[-1].end_timecode,
        text="\n".join(text_lines),
        segment_count=len(items),
    )


def detect_actions(text: str) -> List[str]:
    return _detect_actions(text, limit=8)


def _detect_actions(text: str, limit: int) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    actions: List[str] = []
    for sentence in sentences:
        clean = sentence.strip(" -")
        if not clean:
            continue
        normalized = clean.lower()
        if any(pattern in normalized for pattern in ACTION_PATTERNS):
            actions.append(clean)
        if len(actions) >= limit:
            break
    return actions


def detect_notes(text: str) -> List[str]:
    patterns = ("recuerda", "importante", "seguridad", "debe", "unica vez", "única vez", "solo podras", "solo podrás")
    notes: List[str] = []
    for sentence in split_sentences(text):
        normalized = sentence.lower()
        if any(pattern in normalized for pattern in patterns):
            notes.append(sentence_to_instruction(sentence))
        if len(notes) >= 6:
            break
    return notes


def clean_transcript_text(text: str) -> str:
    cleaned = re.sub(r"\[[0-9:.]+\s+-\s+[0-9:.]+\]\s*", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def split_sentences(text: str) -> List[str]:
    return [item.strip(" -") for item in re.split(r"(?<=[.!?])\s+", text) if item.strip(" -")]


def sentence_to_instruction(sentence: str) -> str:
    cleaned = clean_transcript_text(sentence).strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def summarize_block_text(text: str) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return text
    selected = sentences[:5]
    summary = " ".join(sentence_to_instruction(sentence) for sentence in selected)
    if len(summary) < 220 and len(sentences) > 5:
        summary = " ".join(sentence_to_instruction(sentence) for sentence in sentences[:8])
    return summary


def manual_title(metadata: VideoMetadata) -> str:
    stem = Path(metadata.original_filename).stem.strip() or "capacitacion"
    return f"Manual de capacitacion: {stem}"


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "No disponible"
    total = max(0, int(round(seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60
    if hours:
        return f"{hours}h {minutes}m {remaining}s"
    if minutes:
        return f"{minutes}m {remaining}s"
    return f"{remaining}s"


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def clean_markdown(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def extract_start_timecode(line: str) -> Optional[str]:
    match = re.match(r"\[([0-9:.]+)\s+-\s+[0-9:.]+\]", line)
    return match.group(1) if match else None


def extract_end_timecode(line: str) -> Optional[str]:
    match = re.match(r"\[[0-9:.]+\s+-\s+([0-9:.]+)\]", line)
    return match.group(1) if match else None
