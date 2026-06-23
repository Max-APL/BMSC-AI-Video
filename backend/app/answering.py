from __future__ import annotations

from typing import Any, List, Optional

from .config import Settings
from .manual_generation import get_llm_client, normalize_llm_provider
from .models import AnswerMode, AnswerResponse, SearchMatch


def clean_answer_text(text: str) -> str:
    return " ".join(text.split())


def build_extractive_answer(
    video_id: str,
    question: str,
    matches: List[SearchMatch],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    fallback_reason: Optional[str] = None,
) -> AnswerResponse:
    if not matches:
        return AnswerResponse(
            video_id=video_id,
            question=question,
            answer=(
                "No encontré una coincidencia clara en la transcripción del video. "
                "Prueba reformular la consulta con palabras más parecidas a las usadas en la capacitación."
            ),
            confidence=0.0,
            sources=[],
            mode=AnswerMode.extractive,
            provider=provider,
            model=model,
            fallback_reason=fallback_reason,
        )

    best = matches[0]
    cleaned_text = clean_answer_text(best.text)
    confidence = round(float(best.score), 6)

    if confidence < 0.08:
        answer = (
            "No encontré una respuesta suficientemente clara, pero el fragmento más cercano "
            f"aparece entre {best.start_timecode} y {best.end_timecode}: {cleaned_text}"
        )
    else:
        answer = (
            f"Se habla de esto entre {best.start_timecode} y {best.end_timecode}. "
            f"Según el video: {cleaned_text}"
        )

    return AnswerResponse(
        video_id=video_id,
        question=question,
        answer=answer,
        confidence=confidence,
        sources=matches,
        mode=AnswerMode.extractive,
        provider=provider,
        model=model,
        fallback_reason=fallback_reason,
    )


def build_llm_answer(
    *,
    video_id: str,
    question: str,
    matches: List[SearchMatch],
    settings: Settings,
    provider: str,
    model: str,
    client: Optional[Any] = None,
) -> AnswerResponse:
    resolved_provider = normalize_llm_provider(provider)
    if not matches:
        return build_extractive_answer(
            video_id,
            question,
            matches,
            provider=resolved_provider,
            model=model,
            fallback_reason="No hay fuentes recuperadas para enviar al modelo.",
        )

    llm_client = client or get_llm_client(
        provider=resolved_provider,
        model=model,
        settings=settings,
    )
    answer = llm_client.chat(
        system_prompt=(
            "Eres un asistente corporativo para consultas sobre videos de capacitacion. "
            "Responde solamente con la evidencia entregada. No inventes datos, no uses "
            "conocimiento externo y no menciones al modelo ni a la transcripcion. Si la "
            "evidencia no permite contestar, dilo claramente y sugiere revisar las fuentes."
        ),
        user_prompt=build_answer_prompt(question, matches),
    )
    confidence = round(float(matches[0].score), 6)
    return AnswerResponse(
        video_id=video_id,
        question=question,
        answer=clean_answer_text(answer),
        confidence=confidence,
        sources=matches,
        mode=AnswerMode.llm,
        provider=resolved_provider,
        model=model,
    )


def build_answer_prompt(question: str, matches: List[SearchMatch]) -> str:
    return f"""
Pregunta del usuario:
{question}

Fuentes recuperadas del video:
{format_answer_sources(matches)}

Instrucciones:
- Responde en espanol claro y directo.
- Usa solo las fuentes anteriores.
- Incluye los timecodes relevantes en la respuesta cuando ayuden a ubicar la evidencia.
- No agregues pasos, requisitos, URLs, nombres de productos ni conclusiones que no aparezcan en las fuentes.
- Si hay varias fuentes, sintetiza la respuesta sin repetir texto literal innecesariamente.
- Si las fuentes no responden la pregunta, indica que no hay evidencia suficiente.
""".strip()


def format_answer_sources(matches: List[SearchMatch]) -> str:
    lines: List[str] = []
    for index, match in enumerate(matches, start=1):
        lines.append(
            "\n".join(
                [
                    f"Fuente {index} ({match.start_timecode} - {match.end_timecode}, score {match.score:.3f}):",
                    clean_answer_text(match.text),
                ]
            )
        )
    return "\n\n".join(lines)
