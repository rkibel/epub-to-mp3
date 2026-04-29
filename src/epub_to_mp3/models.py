from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TextSpan:
    text: str
    language: str
    chapter_index: int
    chunk_index: int


@dataclass(slots=True)
class Chapter:
    index: int
    title: str
    text: str
    spans: list[TextSpan] = field(default_factory=list)


@dataclass(slots=True)
class Book:
    title: str
    author: str | None
    chapters: list[Chapter]

