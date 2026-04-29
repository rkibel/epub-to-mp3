from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

from epub_to_mp3.cli import _build_config_from_args, _export_conversion_result, build_parser
from epub_to_mp3.models import Book
from epub_to_mp3.pipeline import ChapterConversionResult, ConversionResult


class CliRoutingArgumentTests(unittest.TestCase):
    def test_defaults_preserve_app_config_routing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["inspect", "book.epub"])

        config = _build_config_from_args(args, parser)

        self.assertEqual(config.routing.chunk_size, 450)

    def test_custom_routing_arguments_override_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["convert", "book.epub", "--output-dir", "out", "--chunk-size", "120"])

        config = _build_config_from_args(args, parser)

        self.assertEqual(config.routing.chunk_size, 120)

    def test_unknown_routing_argument_is_rejected(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["inspect", "book.epub", "--routing-padding", "0"])

    def test_convert_parser_accepts_export_arguments(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["convert", "book.epub", "--output-dir", "out", "--export-format", "m4b", "--export-path", "book.m4b"]
        )

        self.assertEqual(args.export_format, "m4b")
        self.assertEqual(args.export_path, "book.m4b")

    def test_export_parser_defaults_to_m4b(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["export", "output/book"])

        self.assertEqual(args.command, "export")
        self.assertEqual(args.export_format, "m4b")
        self.assertEqual(args.input_dir, "output/book")


class CliExportPathTests(unittest.TestCase):
    def test_export_result_defaults_to_slugged_book_title(self) -> None:
        result = ConversionResult(
            book=Book(title="Sample Novel", author="Example Author", chapters=[]),
            output_dir=Path("output/sample-novel"),
            chapters=[
                ChapterConversionResult(
                    chapter_index=1,
                    title="Chapter 1",
                    output_path=Path("output/sample-novel/001-chapter-1.wav"),
                )
            ],
        )

        with mock.patch("epub_to_mp3.cli.export_chapter_wavs") as export_mock:
            export_mock.return_value = Path("output/sample-novel/sample-novel.m4b")
            _export_conversion_result(result=result, export_format="m4b", export_path=None)

        call = export_mock.call_args
        self.assertIsNotNone(call)
        self.assertEqual(call.kwargs["output_path"], Path("output/sample-novel/sample-novel.m4b"))


if __name__ == "__main__":
    unittest.main()
