from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .config import Settings
from .debug import log_event
from .models import TranscriptSegment, VideoMetadata

_BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
_LLAMA_REPO_ID = "bartowski/Llama-3.2-3B-Instruct-GGUF"
_LLAMA_FILENAME = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"


@dataclass(frozen=True)
class ManualBuildResult:
    content: str
    section_count: int
    word_count: int


@dataclass(frozen=True)
class TranscriptBlock:
    index: int
    start_seconds: float
    end_seconds: float
    start_timecode: str
    end_timecode: str
    text: str
    segment_count: int


ScreenshotReference = Tuple[str, str]
ScreenshotMap = Dict[int, List[ScreenshotReference]]


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
    "presione",
    "haz clic",
    "registra",
    "descarga",
    "actualiza",
    "introduce",
    "escoge",
    "elige",
    "debe",
    "recuerda",
    "verifica",
    "confirma",
    "opcion",
    "opción",
    "al ingresar",
    "al seleccionarla",
    "para registrar",
)


def build_extractive_manual(
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    *,
    chunk_seconds: int,
    include_timestamps: bool,
    generated_at: Optional[str] = None,
    screenshots_by_block: Optional[ScreenshotMap] = None,
) -> ManualBuildResult:
    screenshots_by_block = screenshots_by_block or {}
    blocks = build_time_blocks(segments, chunk_seconds=chunk_seconds)
    title = manual_title(metadata)
    full_text = clean_transcript_text("\n".join(block.text for block in blocks))
    actions = deduplicate_sentences(_detect_actions(full_text, limit=14))
    notes = detect_notes(full_text)
    lines = [
        f"# {title}",
        "",
        "## Objeto",
        "",
        (
            f"Documentar el procedimiento explicado en el video para {manual_subject(metadata).lower()}."
        ),
        "",
        "## Informacion del material",
        "",
        f"- Material de origen: {metadata.original_filename}",
        f"- Duracion aproximada: {format_duration(metadata.duration_seconds)}",
        f"- Fecha de generacion: {format_datetime_lapaz(generated_at)}",
        "- Metodo de generacion: manual extractivo sin LLM",
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

    lines.extend(["", "## Desarrollo detallado", ""])

    for block in blocks:
        section_lines: List[str] = []
        section_text = clean_transcript_text(block.text)
        summary = summarize_block_text(section_text)
        block_actions = deduplicate_sentences(_detect_actions(section_text, limit=8))
        block_notes = detect_notes(section_text)
        section_lines.extend(
            [
                f"### Etapa {block.index}",
                "",
            ]
        )
        section_lines.extend(["**Descripcion**", "", summary, ""])
        if block_actions:
            section_lines.extend(["**Pasos identificados**", ""])
            for action_index, action in enumerate(block_actions, start=1):
                section_lines.append(f"{action_index}. {sentence_to_instruction(action)}")
            section_lines.append("")
        if block_notes:
            section_lines.extend(["**Consideraciones**", ""])
            for note in block_notes:
                section_lines.append(f"- {note}")
            section_lines.append("")
        lines.extend(insert_screenshots_in_lines(section_lines, screenshots_by_block.get(block.index)))
        lines.append("")

    if notes:
        lines.extend(["## Puntos de control", ""])
        for note in deduplicate_sentences(notes):
            lines.append(f"- {note}")
        lines.append("")

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
    generated_at: Optional[str] = None,
    screenshots_by_block: Optional[ScreenshotMap] = None,
    on_progress: Optional[Callable[[str, int, int, str], None]] = None,
) -> ManualBuildResult:
    screenshots_by_block = screenshots_by_block or {}
    blocks = build_text_blocks(
        segments,
        chunk_seconds=settings.manual_llm_chunk_seconds,
        max_chars=settings.manual_llm_chunk_max_chars,
    )
    client = get_llm_client(provider=provider, model=model, settings=settings)
    title = manual_title(metadata)
    lines = build_manual_front_matter(
        metadata,
        title=title,
        generation_label=f"LLM local via {provider}",
        model=model,
        generated_at=generated_at,
    )

    if on_progress:
        on_progress("\n".join(lines).strip() + "\n", 0, len(blocks), "")

    generated_sections: List[str] = []
    for block in blocks:
        prefix = "\n".join(lines).strip() + "\n\n"
        block_screenshots = screenshots_by_block.get(block.index)

        def handle_delta(partial_section: str, delta: str) -> None:
            if on_progress:
                on_progress(prefix + clean_markdown(partial_section), block.index, len(blocks), delta)

        generated = client.generate_section(
            title=title,
            block=block,
            include_timestamps=include_timestamps,
            visual_references=block_screenshots,
            on_delta=handle_delta,
        )
        normalized = normalize_llm_section_markdown(generated)
        normalized = insert_section_screenshots(
            normalized,
            block_screenshots,
        )
        generated_sections.append(normalized)
        if on_progress:
            preview = "\n\n".join(lines + ["## Procedimiento detallado"] + generated_sections)
            on_progress(preview.strip() + "\n", block.index, len(blocks), "")

    lines.extend(build_professional_overview(metadata).splitlines())
    lines.extend(["", "## Procedimiento detallado", ""])
    for generated_section in generated_sections:
        lines.append(generated_section)
        lines.append("")

    lines.extend(
        [
            "## Anexo: referencias de revision",
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


_llama_lock = Lock()
_llama_instance: Optional[Any] = None


def _ensure_llama_model(configured_path: Optional[Path]) -> Path:
    target = configured_path or (_BASE_DIR / "models" / _LLAMA_FILENAME)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    log_event(f"Modelo GGUF no encontrado en {target}. Descargando desde Hugging Face...")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub no esta instalado. Ejecuta: pip install huggingface_hub"
        ) from exc
    downloaded = hf_hub_download(
        repo_id=_LLAMA_REPO_ID,
        filename=_LLAMA_FILENAME,
        local_dir=str(target.parent),
        local_dir_use_symlinks=False,
    )
    log_event(f"Modelo descargado en {downloaded}")
    return Path(downloaded)


def _get_llama_with_options(
    model_path: Optional[Path],
    n_ctx: int,
    n_gpu_layers: int,
    n_threads: int,
    n_threads_batch: int,
    n_batch: int,
    n_ubatch: int,
) -> Any:
    global _llama_instance
    with _llama_lock:
        if _llama_instance is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError(
                    "llama-cpp-python no esta instalado. "
                    'Instala con: CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --force-reinstall --no-cache-dir'
                ) from exc

            gpu_supported = False
            try:
                from llama_cpp import llama_supports_gpu_offload
                gpu_supported = llama_supports_gpu_offload()
                if not gpu_supported:
                    log_event(
                        "ADVERTENCIA: llama-cpp-python NO tiene soporte CUDA. "
                        'Reinstala con: CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --force-reinstall --no-cache-dir'
                    )
                else:
                    log_event("llama-cpp-python: soporte CUDA confirmado")
            except Exception:
                log_event("llama-cpp-python: no se pudo verificar soporte GPU (version antigua?)")

            resolved = _ensure_llama_model(model_path)
            effective_gpu_layers = n_gpu_layers if gpu_supported else 0
            log_event(
                f"Cargando modelo GGUF path={resolved} "
                f"n_ctx={n_ctx} n_gpu_layers={effective_gpu_layers} "
                f"n_threads={n_threads or 'auto'} "
                f"n_threads_batch={n_threads_batch or 'auto'} "
                f"n_batch={n_batch} n_ubatch={n_ubatch}"
            )
            llama_kwargs = {
                "model_path": str(resolved),
                "n_ctx": n_ctx,
                "n_gpu_layers": effective_gpu_layers,
                "n_batch": n_batch,
                "n_ubatch": n_ubatch,
                "verbose": True,
            }
            if n_threads > 0:
                llama_kwargs["n_threads"] = n_threads
            if n_threads_batch > 0:
                llama_kwargs["n_threads_batch"] = n_threads_batch
            try:
                _llama_instance = Llama(**llama_kwargs)
                log_event(
                    f"Modelo GGUF cargado en {'GPU' if effective_gpu_layers != 0 else 'CPU'}"
                )
            except Exception as exc:
                if effective_gpu_layers != 0:
                    log_event(f"Carga en GPU fallo ({exc}); reintentando en CPU")
                    llama_kwargs["n_gpu_layers"] = 0
                    _llama_instance = Llama(**llama_kwargs)
                    log_event("Modelo GGUF cargado en CPU (fallback)")
                else:
                    raise
    return _llama_instance


class LlamaCppClient:
    def __init__(
        self,
        *,
        model_path: Optional[Path],
        n_ctx: int,
        n_gpu_layers: int,
        n_threads: int,
        n_threads_batch: int,
        n_batch: int,
        n_ubatch: int,
        max_tokens_answer: int,
        max_tokens_section: int,
        temperature: float,
        terminology_hints: str,
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.n_threads_batch = n_threads_batch
        self.n_batch = n_batch
        self.n_ubatch = n_ubatch
        self.max_tokens_answer = max_tokens_answer
        self.max_tokens_section = max_tokens_section
        self.temperature = temperature
        self.manual_terminology_hints = terminology_hints

    def generate_section(
        self,
        *,
        title: str,
        block: TranscriptBlock,
        include_timestamps: bool,
        visual_references: Optional[List[ScreenshotReference]] = None,
        on_delta: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        timestamp_instruction = (
            "No insertes timestamps dentro del texto. La trazabilidad se generara en un anexo separado."
            if include_timestamps
            else "No incluyas timestamps."
        )
        system_prompt = (
            "Eres un redactor tecnico senior especializado en manuales operativos "
            "corporativos. Transformas transcripciones en procedimientos claros, "
            "formales y auditables. No inventes datos, no agregues requisitos no "
            "mencionados y no uses informacion externa. Si un dato no aparece en la "
            "transcripcion, omitelo. Corrige errores menores de transcripcion solo "
            "cuando el contexto sea claro. Responde exclusivamente en Markdown simple."
        )
        user_prompt = f"""
Genera una seccion profesional para un manual operativo.

Manual: {title}
Bloque: {block.index}
Rango de video: {block.start_timecode} - {block.end_timecode}
Terminologia preferente: {self.terminology_hints()}
Puntos visuales relevantes del bloque:
{format_visual_references(visual_references)}

Formato obligatorio:
### Titulo claro de la seccion
Parrafo breve que explique el proposito de esta parte.

#### Procedimiento
1. Paso redactado con verbo de accion.
2. Paso redactado con verbo de accion.

#### Consideraciones
- Nota relevante si aparece en la transcripcion.

Instrucciones:
- Escribe en espanol claro y formal.
- No escribas como transcripcion y no pegues dialogos.
- Cada paso debe estar soportado por la transcripcion del bloque.
- Si el bloque solo contiene una explicacion, redacta descripcion y consideraciones; no inventes pasos.
- Las capturas se insertan automaticamente; no las menciones en el texto.
- No uses encabezados subrayados con === o ---.
- No uses asteriscos para vinetas; usa guion medio.
- No menciones al modelo, a la IA ni a la transcripcion.
- No incluyas una seccion de referencias.
- No mezcles vinetas dentro de pasos numerados; si hay alternativas, crea una subseccion "#### Metodos disponibles".
- Cuando existan opciones, botones, campos, codigos o mensajes de confirmacion, describe la accion o resultado asociado si aparece en la transcripcion.
- No omitas estados visibles relevantes del proceso, como confirmaciones, validaciones, codigos recibidos o mensajes en pantalla, si aparecen en la transcripcion.
- Integra los puntos visuales relevantes como pasos, metodos o consideraciones cuando correspondan; no los llames capturas ni imagenes.
- Usa la terminologia preferente cuando la transcripcion tenga variantes foneticas o errores claros.
- {timestamp_instruction}
- Mantente fiel a la transcripcion aunque tenga errores menores.

Transcripcion:
{block.text}
""".strip()
        return self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.max_tokens_section,
            on_delta=on_delta,
        )

    def terminology_hints(self) -> str:
        hints = getattr(self, "manual_terminology_hints", "")
        return hints or "No definida"

    def generate_overview(
        self,
        *,
        title: str,
        transcript_excerpt: str,
        section_summaries: str,
    ) -> str:
        system_prompt = (
            "Eres un redactor tecnico senior. Generas la apertura formal de un "
            "manual operativo corporativo a partir de evidencia textual. No inventes "
            "informacion y no menciones IA, modelo ni transcripcion."
        )
        user_prompt = f"""
Redacta la parte inicial de un manual profesional.

Manual: {title}

Devuelve exactamente estas secciones en Markdown:
## Objeto
Un parrafo especifico y claro.

## Alcance
Un parrafo que indique que cubre el procedimiento, sin agregar datos externos.

Reglas:
- No uses timestamps.
- No escribas generalidades vacias.
- No menciones al modelo, IA ni transcripcion.
- Si no hay datos suficientes, omite el dato en lugar de inventarlo.

Evidencia principal:
{transcript_excerpt}

Secciones generadas:
{section_summaries[:6000]}
""".strip()
        return self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.max_tokens_section,
        )

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        on_delta: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        llm = self._llama()
        resolved_max_tokens = max_tokens or self.max_tokens_answer
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if on_delta is None:
            response = llm.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                max_tokens=resolved_max_tokens,
            )
            content = response["choices"][0]["message"]["content"] or ""
            if not content:
                raise RuntimeError("llama-cpp-python no devolvio contenido.")
            return content

        parts: List[str] = []
        stream = llm.create_chat_completion(
            messages=messages,
            temperature=self.temperature,
            max_tokens=resolved_max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0]["delta"].get("content") or ""
            if delta:
                parts.append(delta)
                on_delta("".join(parts), delta)
        content = "".join(parts).strip()
        if not content:
            raise RuntimeError("llama-cpp-python no devolvio contenido.")
        return content

    def _llama(self):
        return _get_llama_with_options(
            self.model_path,
            self.n_ctx,
            self.n_gpu_layers,
            self.n_threads,
            self.n_threads_batch,
            self.n_batch,
            self.n_ubatch,
        )


def normalize_llm_provider(provider: Optional[str]) -> str:
    normalized = (provider or "llama_cpp").strip().lower().replace("-", "_")
    aliases = {
        "llamacpp": "llama_cpp",
        "llama.cpp": "llama_cpp",
        "llama_cpp": "llama_cpp",
    }
    if normalized not in aliases:
        raise RuntimeError(
            f"Proveedor LLM no soportado: {provider}. Usa 'llama_cpp'."
        )
    return aliases[normalized]


def get_llm_client(*, provider: str, model: str, settings: Settings) -> Any:
    normalize_llm_provider(provider)
    return LlamaCppClient(
        model_path=settings.llm_model_path,
        n_ctx=settings.llm_num_ctx,
        n_gpu_layers=settings.llm_n_gpu_layers,
        n_threads=settings.llm_n_threads,
        n_threads_batch=settings.llm_n_threads_batch,
        n_batch=settings.llm_n_batch,
        n_ubatch=settings.llm_n_ubatch,
        max_tokens_answer=settings.llm_max_tokens_answer,
        max_tokens_section=settings.llm_max_tokens_section,
        temperature=settings.llm_temperature,
        terminology_hints=settings.manual_terminology_hints,
    )

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
            blocks.append(
                TranscriptBlock(
                    len(blocks) + 1,
                    block.start_seconds,
                    block.end_seconds,
                    block.start_timecode,
                    block.end_timecode,
                    block.text,
                    block.segment_count,
                )
            )
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
                        start_seconds=block.start_seconds,
                        end_seconds=block.end_seconds,
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
                    start_seconds=block.start_seconds,
                    end_seconds=block.end_seconds,
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
        start_seconds=items[0].start_seconds,
        end_seconds=items[-1].end_seconds,
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
        if any(normalized.startswith(pattern) for pattern in ACTION_PATTERNS):
            actions.append(clean)
        if len(actions) >= limit:
            break
    return actions


def detect_notes(text: str) -> List[str]:
    patterns = ("recuerda", "importante", "debe", "unica vez", "única vez", "solo podras", "solo podrás")
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


def deduplicate_sentences(sentences: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for sentence in sentences:
        normalized = re.sub(r"\W+", " ", sentence.lower()).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(sentence)
    return result


def append_screenshots(lines: List[str], references: Optional[List[ScreenshotReference]]) -> None:
    if not references:
        return
    lines.extend(["**Capturas clave**", ""])
    for relative_path, caption in references:
        lines.extend([f"![{caption}]({relative_path})", ""])


def format_visual_references(references: Optional[List[ScreenshotReference]]) -> str:
    if not references:
        return "- No se detectaron puntos visuales especificos."
    lines = []
    for _relative_path, caption in references:
        text = trim_context_text(strip_caption_prefix(caption), max_length=220)
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if lines else "- No se detectaron puntos visuales especificos."


def insert_section_screenshots(
    markdown: str,
    references: Optional[List[ScreenshotReference]],
) -> str:
    if not references:
        return markdown
    lines = markdown.splitlines()
    return "\n".join(insert_screenshots_in_lines(lines, references)).strip()


def insert_screenshots_in_lines(
    lines: List[str],
    references: Optional[List[ScreenshotReference]],
) -> List[str]:
    if not references:
        return lines

    result = list(lines)
    positions = find_screenshot_positions(result, references)
    insertion_plan = list(zip(references, positions))
    for (relative_path, caption), line_index in reversed(insertion_plan):
        context = build_screenshot_context_line(caption, result[line_index])
        image_block = [
            "",
            context,
            "",
            f"![{caption}]({relative_path})",
            "",
        ]
        result[line_index + 1:line_index + 1] = image_block
    return result


def find_screenshot_positions(lines: List[str], references: List[ScreenshotReference]) -> List[int]:
    candidate_indexes = [
        index
        for index, line in enumerate(lines)
        if is_screenshot_candidate(line)
    ]
    if not candidate_indexes:
        return [max(0, min(len(lines) - 1, 1))] * len(references)

    used_indexes = set()
    positions: List[int] = []
    for _relative_path, caption in references:
        position = find_best_screenshot_position(caption, lines, candidate_indexes, used_indexes)
        positions.append(position)
        used_indexes.add(position)
    return positions


def is_screenshot_candidate(line: str) -> bool:
    stripped = line.strip()
    return (
        bool(re.match(r"^\d+\.\s+", stripped))
        or is_list_item_candidate(stripped)
        or is_insertable_paragraph(stripped)
    )


def find_best_screenshot_position(
    caption: str,
    lines: List[str],
    candidate_indexes: List[int],
    used_indexes: set[int],
) -> int:
    scored = [
        (text_similarity_score(caption, lines[index]), index)
        for index in candidate_indexes
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))

    unused_scored = [
        (score, index)
        for score, index in scored
        if index not in used_indexes
    ]
    if unused_scored and unused_scored[0][0] > 0:
        return unused_scored[0][1]

    available_indexes = [index for index in candidate_indexes if index not in used_indexes]
    if available_indexes:
        return available_indexes[min(len(used_indexes), len(available_indexes) - 1)]
    return scored[0][1]


def build_screenshot_context_line(caption: str, anchor_line: str) -> str:
    caption_text = trim_context_text(strip_caption_prefix(caption))
    anchor_text = trim_context_text(clean_reference_line(anchor_line))
    score = text_similarity_score(caption, anchor_line)
    if anchor_text and score >= 0.45:
        return f"*La siguiente figura muestra el punto descrito: {ensure_sentence(anchor_text)}*"
    if caption_text:
        return f"*La siguiente figura documenta el punto explicado en el material: {ensure_sentence(caption_text)}*"
    if anchor_text:
        return f"*La siguiente figura complementa el punto descrito: {ensure_sentence(anchor_text)}*"
    return "*La siguiente figura complementa el contenido descrito en esta seccion.*"


def clean_reference_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
    cleaned = re.sub(r"^[-*]\s+", "", cleaned)
    cleaned = cleaned.strip()
    if cleaned.startswith("**") and cleaned.endswith("**"):
        cleaned = cleaned.strip("*")
    return cleaned


def trim_context_text(text: str, max_length: int = 180) -> str:
    cleaned = clean_transcript_text(text).strip(" -")
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip(" ,.;:") + "..."


def ensure_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if cleaned[-1] in ".!?":
        return cleaned
    return cleaned + "."


def text_similarity_score(reference: str, candidate: str) -> float:
    reference_tokens = content_tokens(reference)
    candidate_tokens = content_tokens(candidate)
    if not reference_tokens or not candidate_tokens:
        return 0.0

    reference_set = set(reference_tokens)
    candidate_set = set(candidate_tokens)
    overlap = reference_set & candidate_set
    sequence_bonus = consecutive_token_bonus(reference_tokens, candidate_tokens)
    return (len(overlap) / max(1, len(reference_set))) + sequence_bonus


def consecutive_token_bonus(reference_tokens: List[str], candidate_tokens: List[str]) -> float:
    if not reference_tokens or not candidate_tokens:
        return 0.0
    candidate_pairs = set(zip(candidate_tokens, candidate_tokens[1:]))
    if not candidate_pairs:
        return 0.0
    matched_pairs = sum(
        1
        for pair in zip(reference_tokens, reference_tokens[1:])
        if pair in candidate_pairs
    )
    return min(0.4, matched_pairs * 0.08)


def content_tokens(text: str) -> List[str]:
    normalized = normalize_for_similarity(strip_caption_prefix(text))
    words = re.findall(r"[a-z0-9]+", normalized)
    return [
        normalize_token(word)
        for word in words
        if len(normalize_token(word)) >= 3 and normalize_token(word) not in STOPWORDS
    ]


def strip_caption_prefix(text: str) -> str:
    return re.sub(
        r"^(?:captura de apoyo|figura|imagen de referencia)\s*(?:\([^)]+\))?\s*-\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )


def normalize_for_similarity(text: str) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
        "ü": "u",
    }
    normalized = text.lower()
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def normalize_token(token: str) -> str:
    replacements = {
        "acceda": "ingresar",
        "accede": "ingresar",
        "acceder": "ingresar",
        "actualice": "descargar",
        "actualiza": "descargar",
        "actualizar": "descargar",
        "descarga": "descargar",
        "descargue": "descargar",
        "descargar": "descargar",
        "ingresa": "ingresar",
        "ingrese": "ingresar",
        "ingresar": "ingresar",
        "introduce": "introducir",
        "introduzca": "introducir",
        "introducir": "introducir",
        "selecciona": "seleccionar",
        "seleccione": "seleccionar",
        "seleccionar": "seleccionar",
        "presiona": "presionar",
        "presione": "presionar",
        "presionar": "presionar",
        "pulse": "presionar",
        "pulsar": "presionar",
        "boton": "boton",
        "botones": "boton",
        "campo": "campo",
        "campos": "campo",
        "clave": "codigo",
        "movil": "movil",
        "mobile": "movil",
        "app": "aplicacion",
        "aplicacion": "aplicacion",
        "aplicaciones": "aplicacion",
        "codigo": "codigo",
        "codigos": "codigo",
        "correo": "correo",
        "electronico": "electronico",
        "toquen": "token",
        "token": "token",
        "vestor": "store",
        "store": "store",
        "general": "generar",
    }
    return replacements.get(token, token)


STOPWORDS = {
    "para",
    "con",
    "por",
    "del",
    "los",
    "las",
    "una",
    "uno",
    "este",
    "esta",
    "que",
    "debe",
    "debes",
    "desde",
    "donde",
    "como",
    "captura",
    "apoyo",
    "referencia",
    "visual",
    "paso",
    "procedimiento",
}


def is_insertable_paragraph(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#") or stripped.startswith("!") or stripped.startswith("- "):
        return False
    if stripped.startswith("**") and stripped.endswith("**"):
        return False
    return True


def is_list_item_candidate(line: str) -> bool:
    stripped = line.strip()
    if not re.match(r"^[-*]\s+\S", stripped):
        return False
    return len(content_tokens(stripped)) >= 3


def distribute_indexes(indexes: List[int], count: int) -> List[int]:
    if count <= 0:
        return []
    if len(indexes) >= count:
        if count == 1:
            return [indexes[0]]
        last_index = len(indexes) - 1
        return [
            indexes[round(position * last_index / (count - 1))]
            for position in range(count)
        ]
    return indexes + [indexes[-1]] * (count - len(indexes))


def manual_title(metadata: VideoMetadata) -> str:
    stem = manual_subject(metadata)
    return f"Manual operativo: {stem}"


def build_manual_front_matter(
    metadata: VideoMetadata,
    *,
    title: str,
    generation_label: str,
    model: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> List[str]:
    lines = [
        f"# {title}",
        "",
        "## Datos del documento",
        "",
        f"- Material base: {metadata.original_filename}",
        f"- Duracion aproximada: {format_duration(metadata.duration_seconds)}",
        f"- Fecha de generacion: {format_datetime_lapaz(generated_at)}",
        f"- Tipo de documento: Manual operativo",
        f"- Metodo de generacion: {generation_label}",
    ]
    if model:
        lines.append(f"- Modelo local: {model}")
    lines.append("")
    return lines


def build_professional_overview(metadata: VideoMetadata) -> str:
    process_name = manual_subject(metadata).lower()
    return "\n".join(
        [
            "## Objeto",
            "",
            (
                f"Documentar de forma ordenada el procedimiento explicado en el video sobre {process_name}."
            ),
            "",
            "## Alcance",
            "",
            (
                "El contenido cubre unicamente los pasos, opciones y consideraciones que aparecen "
                "en el material base. No se agregan requisitos, politicas ni datos externos."
            ),
        ]
    )


def humanize_stem(stem: str) -> str:
    text = (stem or "capacitacion").replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" -._")
    return text or "capacitacion"


def manual_subject(metadata: VideoMetadata) -> str:
    text = humanize_stem(Path(metadata.original_filename).stem)
    parts = re.split(r"\s+(como|cómo|para|tutorial|capacitacion|capacitación)\b", text, maxsplit=1, flags=re.IGNORECASE)
    subject = parts[0].strip(" -:._") if parts else text
    return subject or text


def build_transcript_excerpt(segments: List[TranscriptSegment], max_chars: int = 9000) -> str:
    lines = []
    total = 0
    for segment in segments:
        text = clean_transcript_text(segment.text)
        if not text:
            continue
        line = f"- {text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def normalize_overview_markdown(text: str) -> str:
    cleaned = normalize_basic_markdown(text, strip_timecodes=True)
    required_headings = ("## Objeto", "## Alcance")
    if all(heading in cleaned for heading in required_headings):
        return cleaned

    return "\n\n".join(
        [
            "## Objeto",
            "Documentar el procedimiento explicado en el material base.",
            "",
            "## Alcance",
            "Este manual cubre unicamente las acciones y consideraciones explicadas en el material base.",
        ]
    )


def normalize_llm_section_markdown(text: str) -> str:
    cleaned = normalize_basic_markdown(text, strip_timecodes=True)
    lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.rstrip()
        normalized = line.strip().lower()
        if normalized.startswith("referencia de revision") or normalized.startswith("referencias de revision"):
            continue
        if normalized.startswith("referencia:"):
            continue
        if line.startswith("# "):
            line = "### " + line[2:].strip()
        elif line.startswith("## "):
            line = "### " + line[3:].strip()
        lines.append(line)

    result = "\n".join(lines).strip()
    if not result.startswith("### "):
        result = "### Procedimiento\n\n" + result
    return result


def normalize_basic_markdown(text: str, *, strip_timecodes: bool) -> str:
    cleaned = clean_markdown(text)
    raw_lines = cleaned.splitlines()
    lines: List[str] = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index].rstrip()
        next_line = raw_lines[index + 1].strip() if index + 1 < len(raw_lines) else ""
        if line.strip() and re.fullmatch(r"={3,}|-{3,}", next_line):
            lines.append("### " + line.strip("# *"))
            index += 2
            continue
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("* ") or stripped.startswith("+ "):
            line = indent + "- " + stripped[2:]
        if strip_timecodes:
            line = strip_inline_timecodes(line)
        lines.append(line)
        index += 1

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def strip_inline_timecodes(text: str) -> str:
    text = re.sub(r"\s*\([0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3})?(?:\s*-\s*[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3})?)?\)", "", text)
    text = re.sub(r"\[[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3})?\s*-\s*[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3})?\]\s*", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def format_datetime_lapaz(value: Optional[str]) -> str:
    if not value:
        return "No disponible"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    lapaz = timezone(timedelta(hours=-4))
    return parsed.astimezone(lapaz).strftime("%Y-%m-%d %H:%M:%S UTC-04:00")


def compact_datetime_lapaz(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return re.sub(r"\W+", "", value)[:15] or "sin-fecha"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    lapaz = timezone(timedelta(hours=-4))
    return parsed.astimezone(lapaz).strftime("%Y%m%d-%H%M%S")


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
