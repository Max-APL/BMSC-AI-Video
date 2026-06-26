from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import List


@dataclass(frozen=True)
class ReviewIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class ManualReviewReport:
    score: float
    passed: bool
    issues: List[ReviewIssue]
    section_count: int
    word_count: int
    screenshot_count: int

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["issues"] = [asdict(issue) for issue in self.issues]
        return payload


GENERIC_PHRASES = (
    "documentar de forma ordenada",
    "material base",
    "procedimiento explicado en el video",
    "contenido cubre unicamente",
    "no se agregan requisitos",
    "la siguiente figura complementa",
    "la siguiente figura documenta el punto explicado",
    "la siguiente figura muestra el punto descrito",
    "utilice las herramientas",
    "asegúrese de que",
    "de manera efectiva",
    "de manera óptima",
)

GIBBERISH_PATTERNS = [
    r"no se puede utilizar esta captura",
    r"no data available",
    r"carro y un piso",
    r"aporta esta teclado",
    r"oportunidad de aporte",
    r"oportuna para una oportuna",
    r"captura de la imagem",
    r"puntuación que se ha utilizado",
    r"sin_aporte",
]

KNOWN_ASR_ERRORS = [
    "toquen",
    "vestor",
    "debe sin producir",
    "botón general",
    "delegará una clave",
    "una descompletada",
    "fáciletarte",
    "corre en pantalla",
]


def review_manual_content(
    content: str,
    *,
    section_count: int,
    word_count: int,
    screenshot_count: int,
) -> ManualReviewReport:
    issues: List[ReviewIssue] = []
    normalized = content.lower()

    if word_count < 180:
        issues.append(ReviewIssue("too_short", "high", "El manual es demasiado breve."))

    headings = re.findall(r"^###\s+.+", content, flags=re.MULTILINE)
    if section_count <= 0 or not headings:
        issues.append(ReviewIssue("missing_sections", "high", "No se detectaron secciones detalladas."))

    procedure_count = len(re.findall(r"^\d+\.\s+\S", content, flags=re.MULTILINE))
    if procedure_count < 2:
        issues.append(ReviewIssue("few_steps", "medium", "Se detectaron pocos pasos accionables."))

    generic_hits = [phrase for phrase in GENERIC_PHRASES if phrase in normalized]
    if len(generic_hits) >= 2:
        issues.append(
            ReviewIssue(
                "generic_language",
                "medium",
                "El manual conserva frases genericas en la apertura o alcance.",
            )
        )

    image_count = content.count("![")
    if screenshot_count > 0 and image_count == 0:
        issues.append(ReviewIssue("missing_images", "medium", "Hay capturas extraidas pero no insertadas."))

    # Check for gibberish captions
    gibberish_hits = 0
    for pattern in GIBBERISH_PATTERNS:
        if re.search(pattern, normalized):
            gibberish_hits += 1
    if gibberish_hits > 0:
        issues.append(ReviewIssue("gibberish_caption", "high", f"Se encontraron {gibberish_hits} descripciones de imagen inservibles o incoherentes."))

    # Check for ASR errors
    asr_hits = 0
    for asr_err in KNOWN_ASR_ERRORS:
        if asr_err in normalized:
            asr_hits += 1
    if asr_hits > 0:
        issues.append(ReviewIssue("asr_errors", "high", f"Se encontraron {asr_hits} errores de transcripción sin corregir."))

    # Check for excessively long sections without steps (possible hallucination)
    if word_count > 600 and procedure_count < (word_count / 200):
        issues.append(ReviewIssue("hallucination_risk", "medium", "Muchas palabras pero pocos pasos accionables, posible invención de contenido."))

    score = 1.0
    for issue in issues:
        if issue.severity == "high":
            score -= 0.22
        elif issue.severity == "medium":
            score -= 0.12
        else:
            score -= 0.06
    score = max(0.0, round(score, 4))
    return ManualReviewReport(
        score=score,
        passed=score >= 0.78 and not any(issue.severity == "high" for issue in issues),
        issues=issues,
        section_count=section_count,
        word_count=word_count,
        screenshot_count=screenshot_count,
    )
