from __future__ import annotations

import unittest

from epub_to_mp3.audio import concat_synthesis_results, concat_synthesis_results_with_gaps
from epub_to_mp3.tts.base import SynthesisResult


def _pcm16_tone(frame_count: int, amplitude: int = 1000) -> bytes:
    sample = amplitude.to_bytes(2, byteorder="little", signed=True)
    return sample * frame_count


def _result(samples: bytes, sample_rate: int = 1000) -> SynthesisResult:
    return SynthesisResult(
        sample_rate=sample_rate,
        samples=samples,
        audio_format="pcm_s16le",
        channels=1,
        sample_width=2,
    )


class AudioConcatenationTests(unittest.TestCase):
    def test_concat_does_not_insert_default_silence_between_spans(self) -> None:
        first = _result(_pcm16_tone(10))
        second = _result(_pcm16_tone(10))

        combined = concat_synthesis_results([first, second])

        self.assertIsNotNone(combined)
        self.assertEqual(len(combined.samples), 40)

    def test_concat_trims_excess_boundary_silence_but_keeps_small_padding(self) -> None:
        silence = b"\x00\x00"
        first = _result(silence * 100 + _pcm16_tone(10) + silence * 200)
        second = _result(silence * 100 + _pcm16_tone(10) + silence * 200)

        combined = concat_synthesis_results([first, second])

        self.assertIsNotNone(combined)
        self.assertEqual(len(combined.samples), 520)

    def test_concat_can_insert_per_boundary_gaps(self) -> None:
        first = _result(_pcm16_tone(10))
        second = _result(_pcm16_tone(10))
        third = _result(_pcm16_tone(10))

        combined = concat_synthesis_results_with_gaps([(first, 0), (second, 100), (third, 0)])

        self.assertIsNotNone(combined)
        self.assertEqual(len(combined.samples), 260)

    def test_concat_drops_short_isolated_tail_artifacts(self) -> None:
        silence = b"\x00\x00"
        result = _result(_pcm16_tone(10) + silence * 400 + _pcm16_tone(40, amplitude=4000) + silence * 80)

        combined = concat_synthesis_results([result])

        self.assertIsNotNone(combined)
        self.assertEqual(len(combined.samples), 180)


if __name__ == "__main__":
    unittest.main()
