from __future__ import annotations

from pathlib import Path
import unittest

from epub_to_mp3.config import RoutingConfig
from epub_to_mp3.epub_parser import parse_epub
from epub_to_mp3.language_router import LanguageRouter
from epub_to_mp3.models import Chapter


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MULTILINGUAL_FUSION_PATH = FIXTURES_DIR / "multilingual_fusion.epub"
DIALOGUE_SWITCH_PATH = FIXTURES_DIR / "dialogue_switch.epub"
SPANISH_ONLY_PATH = FIXTURES_DIR / "spanish_only.epub"
FRENCH_ONLY_PATH = FIXTURES_DIR / "french_only.epub"
ENGLISH_ONLY_PATH = FIXTURES_DIR / "english_only.epub"


class FixtureEpubParsingTests(unittest.TestCase):
    def test_multilingual_fusion_fixture_skips_front_matter_toc_and_footnotes(self) -> None:
        book = parse_epub(MULTILINGUAL_FUSION_PATH)

        self.assertEqual(book.title, "Multilingual Fusion Demo")
        self.assertEqual(book.author, "Codex Fixture")
        self.assertEqual([chapter.title for chapter in book.chapters], ["Chapter 1", "Chapter 2"])

        combined_text = "\n".join(chapter.text for chapter in book.chapters)
        self.assertNotIn("Table of Contents", combined_text)
        self.assertNotIn("should never be spoken", combined_text)
        self.assertNotIn("Codex Fixture", combined_text)

    def test_dialogue_switch_fixture_parses_single_spoken_chapter(self) -> None:
        book = parse_epub(DIALOGUE_SWITCH_PATH)

        self.assertEqual(book.title, "Dialogue Switch Demo")
        self.assertEqual(book.author, "Codex Fixture")
        self.assertEqual(len(book.chapters), 1)
        self.assertEqual(book.chapters[0].title, "Chapter 1")
        self.assertIn("The guide smiled and spoke in English first.", book.chapters[0].text)

    def test_english_only_fixture_includes_chapter_title_and_short_sentences(self) -> None:
        book = parse_epub(ENGLISH_ONLY_PATH)

        self.assertEqual(book.title, "English Only Demo")
        self.assertEqual(book.author, "Codex Fixture")
        self.assertEqual(len(book.chapters), 1)
        self.assertEqual(book.chapters[0].title, "Chapter 1")
        self.assertIn("Chapter 1 Hello. Welcome.", book.chapters[0].text)


class FixtureLanguageRoutingTests(unittest.TestCase):
    def test_multilingual_fusion_fixture_routes_english_french_and_spanish(self) -> None:
        book = parse_epub(MULTILINGUAL_FUSION_PATH)
        router = LanguageRouter(RoutingConfig(chunk_size=100, minimum_span_length=6))

        languages: set[str] = set()
        for chapter in book.chapters:
            router.route_chapter(chapter)
            languages.update(span.language for span in chapter.spans)

        self.assertEqual(languages, {"en", "es", "fr"})
        self.assertTrue(
            any("Merci d'etre venus ce soir" in span.text and span.language == "fr" for span in book.chapters[0].spans)
        )
        self.assertTrue(
            any("Hola, gracias por venir esta noche." in span.text and span.language == "es" for span in book.chapters[0].spans)
        )

    def test_dialogue_switch_fixture_preserves_language_transitions(self) -> None:
        book = parse_epub(DIALOGUE_SWITCH_PATH)
        router = LanguageRouter(RoutingConfig(chunk_size=80, minimum_span_length=6))

        routed = router.route_chapter(book.chapters[0])
        languages = [span.language for span in routed.spans]

        self.assertIn("en", languages)
        self.assertIn("fr", languages)
        self.assertIn("es", languages)
        self.assertTrue(any("Bonsoir." in span.text and span.language == "fr" for span in routed.spans))
        self.assertTrue(any("Hola." in span.text and span.language == "es" for span in routed.spans))

    def test_dialogue_switch_routes_sentence_level_language_spans(self) -> None:
        book = parse_epub(DIALOGUE_SWITCH_PATH)
        router = LanguageRouter(RoutingConfig(chunk_size=450, minimum_span_length=6))

        routed = router.route_chapter(book.chapters[0])

        self.assertEqual(
            [(span.language, span.text) for span in routed.spans],
            [
                ("en", "Chapter 1 The guide smiled and spoke in English first."),
                ("fr", "Bonsoir. Je suis heureux de vous voir."),
                ("en", "Then the narrator paused and changed languages again."),
                ("es", "Hola. Gracias por escuchar esta breve escena."),
                ("en", "The final line returned to English for a calm ending."),
            ],
        )

    def test_short_plain_english_sentence_routes_to_english(self) -> None:
        chapter = Chapter(index=1, title="Chapter 1", text="No. Hola. Yes.")
        router = LanguageRouter(RoutingConfig(chunk_size=450, minimum_span_length=6))

        routed = router.route_chapter(chapter)

        self.assertEqual(
            [(span.language, span.text) for span in routed.spans],
            [("en", "No."), ("es", "Hola."), ("en", "Yes.")],
        )

    def test_spanish_only_fixture_routes_without_language_switches(self) -> None:
        book = parse_epub(SPANISH_ONLY_PATH)
        router = LanguageRouter(RoutingConfig(chunk_size=450, minimum_span_length=6))

        routed = router.route_chapter(book.chapters[0])

        self.assertEqual({span.language for span in routed.spans}, {"es"})
        self.assertEqual(len(routed.spans), 1)
        self.assertIn("Hola.", routed.spans[0].text)
        self.assertIn("Buenos días.", routed.spans[0].text)

    def test_french_only_fixture_routes_without_language_switches(self) -> None:
        book = parse_epub(FRENCH_ONLY_PATH)
        router = LanguageRouter(RoutingConfig(chunk_size=450, minimum_span_length=6))

        routed = router.route_chapter(book.chapters[0])

        self.assertEqual({span.language for span in routed.spans}, {"fr"})
        self.assertEqual(len(routed.spans), 1)
        self.assertIn("Bonsoir.", routed.spans[0].text)
        self.assertIn("Bonjour.", routed.spans[0].text)

    def test_english_only_fixture_routes_short_sentences_to_english(self) -> None:
        book = parse_epub(ENGLISH_ONLY_PATH)
        router = LanguageRouter(RoutingConfig(chunk_size=450, minimum_span_length=6))

        routed = router.route_chapter(book.chapters[0])

        self.assertEqual({span.language for span in routed.spans}, {"en"})
        self.assertEqual(len(routed.spans), 1)
        self.assertIn("Chapter 1 Hello. Welcome.", routed.spans[0].text)


if __name__ == "__main__":
    unittest.main()
