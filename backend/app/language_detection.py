from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable, Optional


SPANISH_MEETING_WORDS = {
    "ahora",
    "alcance",
    "aplicacion",
    "archivo",
    "boton",
    "capacitacion",
    "clave",
    "codigo",
    "como",
    "configuracion",
    "con",
    "contrasena",
    "correo",
    "cuando",
    "de",
    "del",
    "despues",
    "donde",
    "el",
    "en",
    "entonces",
    "equipo",
    "es",
    "esta",
    "este",
    "finalmente",
    "ingresa",
    "ingresar",
    "la",
    "las",
    "lo",
    "los",
    "mensaje",
    "modulo",
    "opcion",
    "para",
    "paso",
    "pantalla",
    "por",
    "primero",
    "proceso",
    "que",
    "registrar",
    "reunion",
    "revision",
    "selecciona",
    "siguiente",
    "usuario",
    "validacion",
    "vamos",
    "ver",
}

ENGLISH_MEETING_WORDS = {
    "about",
    "access",
    "account",
    "after",
    "and",
    "application",
    "button",
    "click",
    "code",
    "configuration",
    "continue",
    "dashboard",
    "email",
    "enter",
    "file",
    "finally",
    "first",
    "for",
    "from",
    "meeting",
    "message",
    "module",
    "next",
    "now",
    "option",
    "password",
    "process",
    "review",
    "screen",
    "select",
    "step",
    "that",
    "the",
    "then",
    "this",
    "to",
    "training",
    "user",
    "validation",
    "we",
    "when",
    "where",
    "with",
    "you",
}

LANGUAGE_ALIASES = {
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "espanol": "es",
    "español": "es",
    "en": "en",
    "eng": "en",
    "english": "en",
    "ingles": "en",
    "inglés": "en",
    "und": "und",
    "unknown": "und",
    "no determinado": "und",
}


def resolve_transcript_language(
    detected_language: Optional[str],
    texts: Iterable[str],
) -> str:
    heuristic_language = detect_language_from_texts(texts)
    if heuristic_language != "und":
        return heuristic_language

    normalized_detected = normalize_language_code(detected_language)
    if normalized_detected in {"es", "en"}:
        return normalized_detected
    return "und"


def detect_language_from_texts(texts: Iterable[str]) -> str:
    tokens = tokenize(" ".join(texts))
    if not tokens:
        return "und"

    counts = Counter(tokens)
    spanish_score = sum(counts[word] for word in SPANISH_MEETING_WORDS)
    english_score = sum(counts[word] for word in ENGLISH_MEETING_WORDS)
    return choose_language(spanish_score, english_score)


def choose_language(spanish_score: int, english_score: int) -> str:
    winner_score = max(spanish_score, english_score)
    loser_score = min(spanish_score, english_score)
    if winner_score < 5:
        return "und"
    if winner_score < loser_score + 3:
        return "und"
    if loser_score and winner_score < loser_score * 1.2:
        return "und"
    return "es" if spanish_score > english_score else "en"


def normalize_language_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = normalize_text(value)
    return LANGUAGE_ALIASES.get(normalized, normalized[:2] if normalized[:2] in {"es", "en"} else None)


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return re.findall(r"[a-z]+", normalized)


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip()
