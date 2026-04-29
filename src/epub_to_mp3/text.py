from __future__ import annotations

import re


WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'“‘¿¡A-ZÀ-ÖØ-ÞА-Я])")


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def split_sentences(text: str) -> list[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    return [sentence.strip() for sentence in SENTENCE_BOUNDARY_RE.split(cleaned) if sentence.strip()]


def chunk_text(text: str, chunk_size: int) -> list[str]:
    cleaned = normalize_text(text)
    if len(cleaned) <= chunk_size:
        return [cleaned] if cleaned else []

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            split_at = cleaned.rfind(" ", start, end)
            if split_at > start:
                end = split_at

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(cleaned):
            break

        start = end

    return chunks


def chunk_sentences(sentences: list[str], chunk_size: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence)
        separator_length = 1 if current else 0
        if current and current_length + separator_length + sentence_length > chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_length = 0

        if sentence_length > chunk_size:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_length = 0
            chunks.extend(chunk_text(sentence, chunk_size=chunk_size))
            continue

        current.append(sentence)
        current_length += separator_length + sentence_length

    if current:
        chunks.append(" ".join(current))

    return chunks
