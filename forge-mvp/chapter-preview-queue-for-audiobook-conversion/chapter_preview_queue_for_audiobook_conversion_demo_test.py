import unittest

from chapter_preview_queue_for_audiobook_conversion_demo import build_preview


class PreflightPreviewTest(unittest.TestCase):
    def test_build_preview_summarizes_queue(self):
        preview = build_preview({
            "book": "Demo",
            "export_format": "m4b",
            "chapters": [
                {"index": 1, "title": "One", "language": "en", "estimated_minutes": 4},
                {"index": 2, "title": "Deux", "language": "fr", "estimated_minutes": 6},
            ],
        })
        self.assertEqual(preview["chapter_count"], 2)
        self.assertEqual(preview["languages"], ["en", "fr"])
        self.assertEqual(preview["estimated_minutes"], 10.0)
        self.assertEqual(preview["queue"][0]["status"], "ready_for_synthesis")


if __name__ == "__main__":
    unittest.main()