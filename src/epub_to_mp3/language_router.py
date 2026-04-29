from __future__ import annotations

import re

from epub_to_mp3.config import RoutingConfig
from epub_to_mp3.models import Chapter, TextSpan
from epub_to_mp3.text import chunk_sentences, split_sentences


CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
FRENCH_MARKER_RE = re.compile(r"[àâæçéèêëîïôœùûüÿ«»]", re.IGNORECASE)
SPANISH_MARKER_RE = re.compile(r"[áíñóúü¿¡]", re.IGNORECASE)
FRENCH_TOKEN_RE = re.compile(
    r"\b(?:grippe|beaucoup|soir(?:ee)?|bonjour|bonsoir|monsieur|madame|attendez|"
    r"vicomte|majest[ée]|seduisante|petersbourg|oui|cher|chere|suis|heureux|heureuse|"
    r"vous|voir|venus|soir)\b|"
    r"\bmon prince\b|\bla femme\b|\bje suis\b|\bde vous\b",
    re.IGNORECASE,
)
SPANISH_TOKEN_RE = re.compile(
    r"\b(?:hola|gracias|adios|adiós|senor|señor|senora|señora|por favor|buenos dias|buenos días|"
    r"buenas noches|buenas tardes|usted|ustedes|amigo|amiga|hablo|hablas|hablan|quiero|quieres|"
    r"mañana|como estas|cómo estás)\b",
    re.IGNORECASE,
)


class LanguageRouter:
    def __init__(self, config: RoutingConfig) -> None:
        self._config = config
        self._detector = _build_lingua_detector(config.supported_languages)

    def route_chapter(self, chapter: Chapter) -> Chapter:
        spans: list[TextSpan] = []
        for chunk_index, language, chunk in self._iter_routed_chunks(chapter.text):
            spans.append(
                TextSpan(
                    text=chunk,
                    language=language,
                    chapter_index=chapter.index,
                    chunk_index=chunk_index,
                )
            )

        chapter.spans = spans
        return chapter

    def _iter_routed_chunks(self, text: str):
        grouped_sentences: list[str] = []
        grouped_language: str | None = None
        chunk_index = 1

        for sentence in split_sentences(text):
            language = self.detect_language(sentence)
            if grouped_language is None:
                grouped_language = language
            if language != grouped_language and grouped_sentences:
                for chunk in chunk_sentences(grouped_sentences, self._config.chunk_size):
                    yield chunk_index, grouped_language, chunk
                    chunk_index += 1
                grouped_sentences = []
                grouped_language = language

            grouped_sentences.append(sentence)

        if grouped_language is None:
            return

        for chunk in chunk_sentences(grouped_sentences, self._config.chunk_size):
            yield chunk_index, grouped_language, chunk
            chunk_index += 1

    def detect_language(self, text: str) -> str:
        probe = text.strip()
        if len(probe) < self._config.minimum_span_length:
            return _detect_fallback_language(probe)

        marker_override = _detect_marker_language(probe)
        if marker_override != "unknown":
            return marker_override

        if self._detector is None:
            return _detect_fallback_language(probe)

        detected = self._detector.detect_language_of(probe)
        if detected is None:
            return _detect_fallback_language(probe)

        iso_code = detected.iso_code_639_1
        if iso_code is None:
            return _detect_fallback_language(probe)

        iso_name = getattr(iso_code, "name", "")
        if iso_name == "EN":
            override = _override_english_detection(probe)
            if override is not None:
                return override
            return "en"
        if iso_name == "ES":
            return "es"
        if iso_name == "FR":
            return "fr"
        if iso_name == "RU":
            return "ru"
        return _detect_fallback_language(probe)


def _detect_short_span_language(text: str) -> str:
    if not text:
        return "unknown"
    if CYRILLIC_RE.search(text):
        return "ru"
    return _detect_marker_language(text)


def _detect_marker_language(text: str) -> str:
    if SPANISH_MARKER_RE.search(text) or SPANISH_TOKEN_RE.search(text):
        return "es"
    if FRENCH_MARKER_RE.search(text) or FRENCH_TOKEN_RE.search(text):
        return "fr"
    return "unknown"


def _detect_fallback_language(text: str) -> str:
    short_language = _detect_short_span_language(text)
    if short_language != "unknown":
        return short_language
    if text.isascii():
        return "en"
    return "unknown"


def _override_english_detection(text: str) -> str | None:
    if SPANISH_MARKER_RE.search(text) or SPANISH_TOKEN_RE.search(text):
        return "es"
    if FRENCH_MARKER_RE.search(text) or FRENCH_TOKEN_RE.search(text):
        return "fr"
    return None


def _build_lingua_detector(supported_languages: tuple[str, ...]):
    try:
        from lingua import Language, LanguageDetectorBuilder
    except ModuleNotFoundError:
        return None

    language_by_code = {
        "en": Language.ENGLISH,
        "es": Language.SPANISH,
        "fr": Language.FRENCH,
        "ru": Language.RUSSIAN,
    }
    languages = [language_by_code[code] for code in supported_languages if code in language_by_code]
    if not languages:
        return None
    return LanguageDetectorBuilder.from_languages(*languages).build()
