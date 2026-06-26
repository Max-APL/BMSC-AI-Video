from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from .config import Settings
from .debug import log_event
from .manual_generation import (
    ManualBuildResult,
    ScreenshotMap,
    build_llm_manual,
    build_transcript_excerpt,
    count_words,
    get_llm_client,
    normalize_basic_markdown,
)
from .manual_agents import run_agentic_manual_review
from .manual_review import ManualReviewReport, review_manual_content
from .models import ManualQualityMode, TranscriptSegment, VideoMetadata


ArtifactWriter = Callable[[str, dict], None]
ProgressCallback = Callable[[str, int, int, str], None]


def build_fast_llm_manual(
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    *,
    settings: Settings,
    provider: str,
    model: str,
    include_timestamps: bool,
    generated_at: Optional[str],
    screenshots_by_block: Optional[ScreenshotMap],
    on_progress: Optional[ProgressCallback],
    write_artifact: Optional[ArtifactWriter] = None,
) -> ManualBuildResult:
    if write_artifact:
        write_artifact(
            "evidence.json",
            {
                "quality_mode": ManualQualityMode.fast.value,
                "segment_count": len(segments),
                "screenshot_count": sum(len(items) for items in (screenshots_by_block or {}).values()),
            },
        )
    return build_llm_manual(
        metadata,
        segments,
        settings=settings,
        provider=provider,
        model=model,
        include_timestamps=include_timestamps,
        generated_at=generated_at,
        screenshots_by_block=screenshots_by_block,
        on_progress=on_progress,
    )


def build_quality_llm_manual(
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    *,
    settings: Settings,
    provider: str,
    model: str,
    include_timestamps: bool,
    generated_at: Optional[str],
    screenshots_by_block: Optional[ScreenshotMap],
    on_progress: Optional[ProgressCallback],
    write_artifact: Optional[ArtifactWriter] = None,
) -> ManualBuildResult:
    screenshots_by_block = screenshots_by_block or {}
    if write_artifact:
        write_artifact(
            "evidence.json",
            {
                "quality_mode": ManualQualityMode.quality.value,
                "segment_count": len(segments),
                "transcript_excerpt": build_transcript_excerpt(segments, max_chars=5000),
                "screenshot_count": sum(len(items) for items in screenshots_by_block.values()),
            },
        )

    result = build_llm_manual(
        metadata,
        segments,
        settings=settings,
        provider=provider,
        model=model,
        include_timestamps=include_timestamps,
        generated_at=generated_at,
        screenshots_by_block=screenshots_by_block,
        on_progress=on_progress,
    )

    review = review_manual_content(
        result.content,
        section_count=result.section_count,
        word_count=result.word_count,
        screenshot_count=sum(len(items) for items in screenshots_by_block.values()),
    )
    if write_artifact:
        write_artifact("review_report.json", review.to_dict())

    try:
        agentic_review = run_agentic_manual_review(
            result.content,
            metadata=metadata,
            segments=segments,
            screenshots_by_block=screenshots_by_block,
            heuristic_review=review,
            client=get_llm_client(provider=provider, model=model, settings=settings),
            max_tokens=max(settings.llm_max_tokens_section, 1600),
        )
        if write_artifact:
            write_artifact("agent_fidelity_report.json", agentic_review.fidelity_report.to_dict())
            write_artifact("agent_visual_report.json", agentic_review.visual_report.to_dict())
            write_artifact("agent_editor_report.json", agentic_review.editor_report.to_dict())
            write_artifact("agentic_review_summary.json", agentic_review.summary_dict())
        if agentic_review.repaired:
            result = ManualBuildResult(
                content=agentic_review.content,
                section_count=result.section_count,
                word_count=count_words(agentic_review.content),
            )
            review = review_manual_content(
                result.content,
                section_count=result.section_count,
                word_count=result.word_count,
                screenshot_count=sum(len(items) for items in screenshots_by_block.values()),
            )
            if write_artifact:
                write_artifact("review_report_agentic.json", review.to_dict())
    except Exception as exc:
        log_event(f"Revision agentica del manual fallo; se conserva version previa: {exc}", metadata.id)

    max_loops = max(0, min(2, settings.manual_quality_max_loops))
    if review.score >= settings.manual_min_review_score or max_loops <= 0:
        return result

    repaired_content = result.content
    current_review = review
    for loop_index in range(max_loops):
        try:
            repaired_content = repair_manual_with_llm(
                repaired_content,
                current_review,
                metadata=metadata,
                segments=segments,
                settings=settings,
                provider=provider,
                model=model,
            )
        except Exception as exc:
            log_event(f"Reparacion agentica del manual fallo; se conserva version previa: {exc}", metadata.id)
            break

        current_review = review_manual_content(
            repaired_content,
            section_count=result.section_count,
            word_count=count_words(repaired_content),
            screenshot_count=sum(len(items) for items in screenshots_by_block.values()),
        )
        if write_artifact:
            write_artifact(
                f"review_report_repair_{loop_index + 1}.json",
                current_review.to_dict(),
            )
        if current_review.score >= settings.manual_min_review_score:
            break

    return ManualBuildResult(
        content=repaired_content,
        section_count=result.section_count,
        word_count=count_words(repaired_content),
    )


def repair_manual_with_llm(
    content: str,
    review: ManualReviewReport,
    *,
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    settings: Settings,
    provider: str,
    model: str,
) -> str:
    client = get_llm_client(provider=provider, model=model, settings=settings)
    issues = "\n".join(f"- {issue.code}: {issue.message}" for issue in review.issues)
    prompt = f"""
Corrige el siguiente manual operativo sin cambiar su formato Markdown principal.

Objetivo:
- Reducir lenguaje generico.
- Mantener solo informacion soportada por la evidencia.
- Mejorar pasos accionables cuando la evidencia lo permita.
- Mantener las imagenes existentes en su lugar si aportan.
- No agregues datos externos ni politicas no mencionadas.

Problemas detectados:
{issues or "- Sin problemas criticos, mejora redaccion y especificidad."}

Evidencia disponible:
{build_transcript_excerpt(segments, max_chars=7000)}

Manual actual:
{content[:12000]}
""".strip()
    repaired = client.chat(
        system_prompt=(
            "Eres un revisor tecnico senior de manuales operativos. "
            "Devuelves exclusivamente Markdown corregido, fiel a la evidencia."
        ),
        user_prompt=prompt,
        max_tokens=max(settings.llm_max_tokens_section, 1600),
    )
    repaired = normalize_basic_markdown(repaired, strip_timecodes=False)
    return repaired.strip() + "\n"
