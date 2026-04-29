from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from epub_to_mp3.audio import concat_synthesis_results_with_gaps, write_wav_file
from epub_to_mp3.config import AppConfig
from epub_to_mp3.epub_parser import parse_epub
from epub_to_mp3.language_router import LanguageRouter
from epub_to_mp3.models import Book, Chapter, TextSpan
from epub_to_mp3.tts.base import SynthesisResult, TTSBackend
from epub_to_mp3.tts.factory import build_tts_registry


@dataclass(slots=True)
class ChapterConversionResult:
    chapter_index: int
    title: str
    output_path: Path | None
    rendered_spans: int = 0
    skipped_spans: int = 0
    rendered_languages: dict[str, int] = field(default_factory=dict)
    skipped_languages: dict[str, int] = field(default_factory=dict)
    skip_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConversionResult:
    book: Book
    output_dir: Path
    chapters: list[ChapterConversionResult]
    audio_format: str = "wav"

    @property
    def rendered_spans(self) -> int:
        return sum(chapter.rendered_spans for chapter in self.chapters)

    @property
    def skipped_spans(self) -> int:
        return sum(chapter.skipped_spans for chapter in self.chapters)

    @property
    def rendered_chapters(self) -> int:
        return sum(1 for chapter in self.chapters if chapter.output_path is not None)


def inspect_book(epub_path: str | Path, config: AppConfig) -> Book:
    book = parse_epub(epub_path)
    router = LanguageRouter(config.routing)
    for chapter in book.chapters:
        router.route_chapter(chapter)
    return book


def run_conversion(epub_path: str | Path, output_dir: str | Path, config: AppConfig) -> ConversionResult:
    book = inspect_book(epub_path, config)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    tts_registry = build_tts_registry(config)
    chapter_results: list[ChapterConversionResult] = []

    for chapter in book.chapters:
        chapter_result = _render_chapter(
            chapter=chapter,
            output_dir=output_path,
            tts_registry=tts_registry,
        )
        chapter_results.append(chapter_result)

    return ConversionResult(book=book, output_dir=output_path, chapters=chapter_results)


def _render_chapter(
    chapter: Chapter,
    output_dir: Path,
    tts_registry: dict[str, TTSBackend],
) -> ChapterConversionResult:
    rendered_audio: list[tuple[str, SynthesisResult]] = []
    chapter_result = ChapterConversionResult(
        chapter_index=chapter.index,
        title=chapter.title,
        output_path=None,
    )

    for span in chapter.spans:
        synthesis, error = _synthesize_span(span=span, tts_registry=tts_registry)
        if synthesis is None:
            chapter_result.skipped_spans += 1
            chapter_result.skipped_languages[span.language] = (
                chapter_result.skipped_languages.get(span.language, 0) + 1
            )
            if error and error not in chapter_result.skip_reasons:
                chapter_result.skip_reasons.append(error)
            continue

        rendered_audio.append((span.language, synthesis))
        chapter_result.rendered_spans += 1
        chapter_result.rendered_languages[span.language] = (
            chapter_result.rendered_languages.get(span.language, 0) + 1
        )

    chapter_audio = _concat_rendered_spans(rendered_audio)
    if chapter_audio is None:
        return chapter_result

    chapter_path = output_dir / f"{chapter.index:03d}-{_slugify(chapter.title)}.wav"
    chapter_result.output_path = write_wav_file(chapter_path, chapter_audio)
    return chapter_result


def _synthesize_span(
    span: TextSpan,
    tts_registry: dict[str, TTSBackend],
) -> tuple[SynthesisResult | None, str | None]:
    backend = tts_registry.get(span.language)
    if backend is None:
        return None, f"No backend is configured for language '{span.language}'."

    try:
        return backend.synthesize(span.text), None
    except NotImplementedError as exc:
        return None, str(exc)
    except Exception as exc:  # pragma: no cover - defensive reporting path
        return None, f"{span.language} synthesis failed: {exc}"


def _concat_rendered_spans(rendered_audio: list[tuple[str, SynthesisResult]]) -> SynthesisResult | None:
    synthesis_with_gaps: list[tuple[SynthesisResult, int]] = []
    previous_language: str | None = None
    for language, synthesis in rendered_audio:
        leading_silence_ms = 100 if previous_language is not None and language != previous_language else 0
        synthesis_with_gaps.append((synthesis, leading_silence_ms))
        previous_language = language
    return concat_synthesis_results_with_gaps(synthesis_with_gaps)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "chapter"
