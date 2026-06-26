from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, List, Optional

from .manual_generation import ScreenshotMap, build_transcript_excerpt, count_words, normalize_basic_markdown
from .manual_review import ManualReviewReport
from .models import TranscriptSegment, VideoMetadata


@dataclass(frozen=True)
class AgentIssue:
    code: str
    severity: str
    message: str
    section: Optional[str] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass(frozen=True)
class AgentReport:
    agent_name: str
    score: float
    passed: bool
    issues: List[AgentIssue] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["issues"] = [asdict(issue) for issue in self.issues]
        return payload


@dataclass(frozen=True)
class AgenticReviewResult:
    content: str
    fidelity_report: AgentReport
    visual_report: AgentReport
    editor_report: AgentReport
    repaired: bool

    def summary_dict(self) -> dict:
        return {
            "repaired": self.repaired,
            "reports": [
                self.fidelity_report.to_dict(),
                self.visual_report.to_dict(),
                self.editor_report.to_dict(),
            ],
        }


def run_agentic_manual_review(
    content: str,
    *,
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    screenshots_by_block: ScreenshotMap,
    heuristic_review: ManualReviewReport,
    client: Any,
    max_tokens: int,
) -> AgenticReviewResult:
    fidelity_report = run_fidelity_agent(
        content,
        metadata=metadata,
        segments=segments,
        client=client,
        max_tokens=max_tokens,
    )
    visual_report = run_visual_agent(
        content,
        screenshots_by_block=screenshots_by_block,
        segments=segments,
        client=client,
        max_tokens=max_tokens,
    )
    editor_content, editor_report = run_editor_agent(
        content,
        metadata=metadata,
        segments=segments,
        heuristic_review=heuristic_review,
        agent_reports=[fidelity_report, visual_report],
        client=client,
        max_tokens=max_tokens,
    )
    return AgenticReviewResult(
        content=editor_content,
        fidelity_report=fidelity_report,
        visual_report=visual_report,
        editor_report=editor_report,
        repaired=editor_content.strip() != content.strip(),
    )


def run_fidelity_agent(
    content: str,
    *,
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    client: Any,
    max_tokens: int,
) -> AgentReport:
    prompt = f"""
Evalua la fidelidad del manual contra la evidencia de transcripcion.

Manual: {metadata.original_filename}

Devuelve exclusivamente JSON con esta forma:
{{
  "score": 0.0,
  "passed": false,
  "issues": [
    {{
      "code": "unsupported_claim",
      "severity": "high",
      "message": "descripcion breve",
      "section": "seccion afectada",
      "evidence": "fragmento de transcripcion o null",
      "recommendation": "accion concreta"
    }}
  ],
  "recommended_actions": ["accion"]
}}

Criterios:
- Marca pasos, botones, menus, campos, sistemas o procedimientos que no esten soportados.
- Marca secciones de instalacion, configuracion, mantenimiento o alertas si la transcripcion no las explica.
- No penalices una redaccion formal si mantiene el sentido de la evidencia.
- Usa severidad high para invencion operativa, medium para ambiguedad importante y low para estilo.

Evidencia:
{build_transcript_excerpt(segments, max_chars=9000)}

Manual:
{content[:14000]}
""".strip()
    return _run_json_report_agent(
        "fidelity",
        client=client,
        system_prompt=(
            "Eres un auditor de fidelidad documental. Detectas contenido no soportado "
            "por la transcripcion y respondes solo JSON valido."
        ),
        user_prompt=prompt,
        max_tokens=max(max_tokens, 1200),
    )


def run_visual_agent(
    content: str,
    *,
    screenshots_by_block: ScreenshotMap,
    segments: List[TranscriptSegment],
    client: Any,
    max_tokens: int,
) -> AgentReport:
    references = _format_screenshot_references(screenshots_by_block)
    if not references:
        return AgentReport(
            agent_name="visual",
            score=1.0,
            passed=True,
            notes="No hay capturas para auditar.",
        )

    deterministic_issues = _detect_visual_issues(content, screenshots_by_block)
    prompt = f"""
Evalua si las capturas incluidas son utiles para un manual operativo.

Devuelve exclusivamente JSON con esta forma:
{{
  "score": 0.0,
  "passed": false,
  "issues": [
    {{
      "code": "low_relevance_image",
      "severity": "medium",
      "message": "descripcion breve",
      "section": "bloque o ruta de imagen",
      "evidence": "caption o texto del bloque",
      "recommendation": "mantener, mover o remover"
    }}
  ],
  "recommended_actions": ["accion"]
}}

Criterios:
- Una captura es util si apoya un paso, pantalla, formulario, menu, confirmacion, validacion o estado visible.
- Penaliza capturas genericas, captions incoherentes, duplicados conceptuales o imagenes sin aporte.
- Si una captura es util pero esta mal explicada, recomienda ajustar caption; no pidas datos externos.

Capturas por bloque:
{references}

Evidencia textual:
{build_transcript_excerpt(segments, max_chars=6000)}

Manual:
{content[:10000]}
""".strip()
    report = _run_json_report_agent(
        "visual",
        client=client,
        system_prompt=(
            "Eres un auditor visual de manuales operativos. Evaluas relevancia "
            "procedural de capturas y respondes solo JSON valido."
        ),
        user_prompt=prompt,
        max_tokens=max(max_tokens, 1000),
    )
    if deterministic_issues:
        issues = list(report.issues) + deterministic_issues
        score = _score_from_issues(issues)
        return AgentReport(
            agent_name="visual",
            score=min(report.score, score),
            passed=report.passed and not _has_actionable_issues(issues),
            issues=issues,
            recommended_actions=report.recommended_actions,
            notes=report.notes,
        )
    return report


def run_editor_agent(
    content: str,
    *,
    metadata: VideoMetadata,
    segments: List[TranscriptSegment],
    heuristic_review: ManualReviewReport,
    agent_reports: Iterable[AgentReport],
    client: Any,
    max_tokens: int,
) -> tuple[str, AgentReport]:
    reports = list(agent_reports)
    if not _should_repair(heuristic_review, reports):
        return content, AgentReport(
            agent_name="editor",
            score=1.0,
            passed=True,
            notes="No se detectaron problemas accionables para reparar.",
        )

    issues = _format_issues_for_editor(heuristic_review, reports)
    prompt = f"""
Corrige el siguiente manual operativo usando exclusivamente la evidencia.

Objetivo:
- Eliminar o suavizar contenido no soportado por la transcripcion.
- Mejorar claridad accionable cuando la evidencia lo permita.
- Corregir errores obvios de transcripcion solo si el contexto es claro.
- Remover imagenes o captions marcadas como inutiles por los reportes.
- Mantener el formato Markdown principal.
- No agregar datos externos.

Problemas detectados:
{issues}

Evidencia disponible:
{build_transcript_excerpt(segments, max_chars=9000)}

Manual actual:
{content[:14000]}
""".strip()
    try:
        repaired = client.chat(
            system_prompt=(
                "Eres el editor final de un manual operativo corporativo. "
                "Devuelves exclusivamente Markdown corregido y fiel a la evidencia."
            ),
            user_prompt=prompt,
            max_tokens=max(max_tokens, 1600),
        )
        repaired = normalize_basic_markdown(repaired, strip_timecodes=False).strip() + "\n"
        return repaired, AgentReport(
            agent_name="editor",
            score=1.0,
            passed=True,
            recommended_actions=["manual_repaired"],
            notes=f"Manual reparado. Palabras finales: {count_words(repaired)}.",
        )
    except Exception as exc:
        return content, AgentReport(
            agent_name="editor",
            score=0.0,
            passed=False,
            issues=[
                AgentIssue(
                    code="editor_failed",
                    severity="low",
                    message=f"No se pudo reparar el manual: {exc}",
                    recommendation="Conservar version previa.",
                )
            ],
            recommended_actions=["kept_previous_version"],
        )


def _run_json_report_agent(
    agent_name: str,
    *,
    client: Any,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> AgentReport:
    try:
        raw = client.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
        payload = _extract_json_object(raw)
        return _report_from_payload(agent_name, payload)
    except Exception as exc:
        return AgentReport(
            agent_name=agent_name,
            score=1.0,
            passed=True,
            issues=[
                AgentIssue(
                    code="agent_unavailable",
                    severity="low",
                    message=f"El agente no devolvio un reporte valido: {exc}",
                    recommendation="No bloquear la generacion; revisar artifact.",
                )
            ],
            recommended_actions=["agent_report_unavailable"],
        )


def _extract_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _report_from_payload(agent_name: str, payload: dict) -> AgentReport:
    issues = []
    for item in payload.get("issues") or []:
        if not isinstance(item, dict):
            continue
        issues.append(
            AgentIssue(
                code=str(item.get("code") or "issue"),
                severity=_normalize_severity(item.get("severity")),
                message=str(item.get("message") or "Problema detectado."),
                section=_optional_str(item.get("section")),
                evidence=_optional_str(item.get("evidence")),
                recommendation=_optional_str(item.get("recommendation")),
            )
        )
    score = _clamp_float(payload.get("score"), _score_from_issues(issues))
    passed = bool(payload.get("passed", score >= 0.78 and not _has_actionable_issues(issues)))
    actions = [
        str(action)
        for action in (payload.get("recommended_actions") or [])
        if str(action).strip()
    ]
    return AgentReport(
        agent_name=agent_name,
        score=score,
        passed=passed,
        issues=issues,
        recommended_actions=actions,
        notes=_optional_str(payload.get("notes")),
    )


def _detect_visual_issues(content: str, screenshots_by_block: ScreenshotMap) -> List[AgentIssue]:
    issues: List[AgentIssue] = []
    for _block_index, refs in screenshots_by_block.items():
        for relative_path, caption in refs:
            if relative_path not in content:
                issues.append(
                    AgentIssue(
                        code="image_not_inserted",
                        severity="medium",
                        message="La captura fue seleccionada pero no aparece en el manual.",
                        section=relative_path,
                        evidence=caption,
                        recommendation="Insertar o descartar explicitamente la captura.",
                    )
                )
            if _looks_like_bad_caption(caption):
                issues.append(
                    AgentIssue(
                        code="bad_visual_caption",
                        severity="high",
                        message="La captura conserva una descripcion incoherente o sin aporte.",
                        section=relative_path,
                        evidence=caption,
                        recommendation="Remover la captura o reemplazar la descripcion con evidencia clara.",
                    )
                )
    return issues


def _looks_like_bad_caption(caption: str) -> bool:
    normalized = caption.lower()
    patterns = (
        "sin_aporte",
        "no se puede utilizar",
        "no data available",
        "carro y un piso",
        "oportunidad de aporte",
        "captura de la imagem",
        "puntuacion que se ha utilizado",
        "puntuación que se ha utilizado",
    )
    return any(pattern in normalized for pattern in patterns)


def _format_screenshot_references(screenshots_by_block: ScreenshotMap) -> str:
    lines: List[str] = []
    for block_index, refs in sorted(screenshots_by_block.items()):
        for relative_path, caption in refs:
            lines.append(f"- Bloque {block_index}: {relative_path} | {caption}")
    return "\n".join(lines)


def _format_issues_for_editor(
    heuristic_review: ManualReviewReport,
    agent_reports: Iterable[AgentReport],
) -> str:
    lines: List[str] = []
    for issue in heuristic_review.issues:
        lines.append(f"- heuristico/{issue.severity}/{issue.code}: {issue.message}")
    for report in agent_reports:
        for issue in report.issues:
            detail = issue.message
            if issue.section:
                detail += f" | seccion: {issue.section}"
            if issue.evidence:
                detail += f" | evidencia: {issue.evidence}"
            if issue.recommendation:
                detail += f" | recomendacion: {issue.recommendation}"
            lines.append(f"- {report.agent_name}/{issue.severity}/{issue.code}: {detail}")
    return "\n".join(lines) if lines else "- Sin problemas criticos."


def _should_repair(heuristic_review: ManualReviewReport, reports: Iterable[AgentReport]) -> bool:
    if not heuristic_review.passed:
        return True
    return any(_has_actionable_issues(report.issues) for report in reports)


def _has_actionable_issues(issues: Iterable[AgentIssue]) -> bool:
    return any(issue.severity in {"high", "medium"} for issue in issues)


def _score_from_issues(issues: Iterable[AgentIssue]) -> float:
    score = 1.0
    for issue in issues:
        if issue.severity == "high":
            score -= 0.25
        elif issue.severity == "medium":
            score -= 0.14
        else:
            score -= 0.05
    return round(max(0.0, score), 4)


def _normalize_severity(value: Any) -> str:
    severity = str(value or "medium").strip().lower()
    return severity if severity in {"high", "medium", "low"} else "medium"


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(0.0, min(1.0, number)), 4)
