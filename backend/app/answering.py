from __future__ import annotations

from typing import List

from .models import AnswerResponse, SearchMatch


def clean_answer_text(text: str) -> str:
    return " ".join(text.split())


def build_extractive_answer(video_id: str, question: str, matches: List[SearchMatch]) -> AnswerResponse:
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
    )
