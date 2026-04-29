from __future__ import annotations

import unittest

from epub_to_mp3.pipeline import _concat_rendered_spans
from epub_to_mp3.tts.base import SynthesisResult


def _result(frame_count: int, sample_rate: int = 1000) -> SynthesisResult:
    return SynthesisResult(
        sample_rate=sample_rate,
        samples=(1000).to_bytes(2, byteorder="little", signed=True) * frame_count,
        audio_format="pcm_s16le",
        channels=1,
        sample_width=2,
    )


class PipelineAudioJoinTests(unittest.TestCase):
    def test_concat_rendered_spans_adds_gap_only_on_language_switches(self) -> None:
        combined = _concat_rendered_spans(
            [
                ("en", _result(10)),
                ("en", _result(10)),
                ("es", _result(10)),
                ("es", _result(10)),
                ("en", _result(10)),
            ]
        )

        self.assertIsNotNone(combined)
        self.assertEqual(len(combined.samples), 500)


if __name__ == "__main__":
    unittest.main()
