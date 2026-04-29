from __future__ import annotations

import argparse
from pathlib import Path
import sys

from epub_to_mp3.config import AppConfig
from epub_to_mp3.exporter import SUPPORTED_EXPORT_FORMATS, export_chapter_wavs, export_wav_directory
from epub_to_mp3.pipeline import ConversionResult, inspect_book, run_conversion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epub-to-mp3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect chapter parsing and language routing.")
    inspect_parser.add_argument("epub_path")
    inspect_parser.add_argument("--max-chapters", type=_positive_int, default=3)
    _add_routing_arguments(inspect_parser)

    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert an EPUB into chapter audio, rendering supported spans and reporting skipped ones.",
    )
    convert_parser.add_argument("epub_path")
    convert_parser.add_argument("--output-dir", default="output")
    convert_parser.add_argument(
        "--export-format",
        choices=SUPPORTED_EXPORT_FORMATS,
        help="Optionally package rendered chapter WAVs into a single listening file.",
    )
    convert_parser.add_argument(
        "--export-path",
        help="Optional output path for the exported MP3/M4B file. If omitted, a file is created inside the output directory.",
    )
    _add_routing_arguments(convert_parser)

    export_parser = subparsers.add_parser(
        "export",
        help="Combine an existing directory of chapter WAV files into a single MP3 or M4B file.",
    )
    export_parser.add_argument("input_dir")
    export_parser.add_argument(
        "--format",
        dest="export_format",
        choices=SUPPORTED_EXPORT_FORMATS,
        default="m4b",
        help="Listening-file format to produce. Defaults to m4b.",
    )
    export_parser.add_argument("--output-file")
    export_parser.add_argument("--title", help="Book title to embed in the exported file metadata.")
    export_parser.add_argument("--author", help="Author name to embed in the exported file metadata.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = _build_config_from_args(args, parser)

    if args.command == "inspect":
        book = inspect_book(args.epub_path, config)
        print(f"Title: {book.title}")
        if book.author:
            print(f"Author: {book.author}")
        print(f"Chapters: {len(book.chapters)}")
        print(
            "Routing: "
            f"chunk_size={config.routing.chunk_size}, "
            f"minimum_span_length={config.routing.minimum_span_length}"
        )

        for chapter in book.chapters[: args.max_chapters]:
            print("")
            print(f"[Chapter {chapter.index}] {chapter.title}")
            for span in chapter.spans[:5]:
                preview = span.text[:90].replace("\n", " ")
                print(f"  - ({span.language}) {preview}")
        return

    if args.command == "convert":
        result = run_conversion(args.epub_path, Path(args.output_dir), config)
        _print_conversion_summary(result, config)
        if result.rendered_chapters == 0:
            print("No audio files were produced. See chapter notes above for the reasons.", file=sys.stderr)
            raise SystemExit(1)
        if args.export_format:
            export_path = _export_conversion_result(
                result=result,
                export_format=args.export_format,
                export_path=args.export_path,
            )
            print(f"Exported listening file: {export_path}")
        return

    if args.command == "export":
        export_path = export_wav_directory(
            args.input_dir,
            output_path=args.output_file,
            export_format=args.export_format,
            book_title=args.title,
            author=args.author,
        )
        print(f"Exported listening file: {export_path}")
        return

    parser.error("Unknown command")


def _print_conversion_summary(result: ConversionResult, config: AppConfig) -> None:
    print(f"Title: {result.book.title}")
    if result.book.author:
        print(f"Author: {result.book.author}")
    print(f"Output format: {result.audio_format.upper()}")
    print(f"Output directory: {result.output_dir}")
    print(f"Chapters processed: {len(result.book.chapters)}")
    print(
        "Routing: "
        f"chunk_size={config.routing.chunk_size}, "
        f"minimum_span_length={config.routing.minimum_span_length}"
    )
    print(f"Rendered spans: {result.rendered_spans}")
    print(f"Skipped spans: {result.skipped_spans}")

    for chapter in result.chapters:
        status = "rendered" if chapter.output_path else "skipped"
        print("")
        print(f"[Chapter {chapter.chapter_index}] {chapter.title} ({status})")
        if chapter.output_path:
            print(f"  - file: {chapter.output_path}")
        if chapter.rendered_languages:
            print(f"  - rendered: {_format_language_counts(chapter.rendered_languages)}")
        if chapter.skipped_languages:
            print(f"  - skipped: {_format_language_counts(chapter.skipped_languages)}")
        for reason in chapter.skip_reasons:
            print(f"  - note: {reason}")


def _format_language_counts(counts: dict[str, int]) -> str:
    parts = [f"{language}={count}" for language, count in sorted(counts.items())]
    return ", ".join(parts)


def _add_routing_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--chunk-size",
        type=_positive_int,
        help="Maximum characters per routing chunk before language detection and synthesis.",
    )


def _build_config_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> AppConfig:
    config = AppConfig()

    if getattr(args, "chunk_size", None) is not None:
        config.routing.chunk_size = args.chunk_size

    return config


def _export_conversion_result(
    *,
    result: ConversionResult,
    export_format: str,
    export_path: str | None,
) -> Path:
    chapter_paths = [chapter.output_path for chapter in result.chapters if chapter.output_path is not None]
    chapter_titles = [chapter.title for chapter in result.chapters if chapter.output_path is not None]
    resolved_export_path = Path(export_path) if export_path else result.output_dir / f"{_slugify(result.book.title)}.{export_format}"
    return export_chapter_wavs(
        chapter_paths=chapter_paths,
        output_path=resolved_export_path,
        book_title=result.book.title,
        author=result.book.author,
        chapter_titles=chapter_titles,
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("Value must be a positive integer.")
    return parsed


def _slugify(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "-" for character in value)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "audiobook"


if __name__ == "__main__":
    main()
