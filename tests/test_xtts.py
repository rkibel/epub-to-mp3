from __future__ import annotations

from pathlib import Path
import unittest

from epub_to_mp3.tts.xtts import XTTSBackend


class FakeTTS:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def tts(self, **kwargs):
        self.calls.append(kwargs)
        return [0.25] * 10


class XTTSBackendTests(unittest.TestCase):
    def test_synthesizes_whole_span_without_xtts_internal_sentence_splitting(self) -> None:
        fake_tts = FakeTTS()
        backend = XTTSBackend(language="es", speaker_wav=Path("speaker.wav"), model_name="fake-model")
        backend._get_tts = lambda: fake_tts

        result = backend.synthesize("Hola. Gracias por escuchar.")

        self.assertEqual(result.sample_rate, 24000)
        self.assertEqual(len(fake_tts.calls), 1)
        self.assertEqual(fake_tts.calls[0]["text"], "Hola. Gracias por escuchar.")
        self.assertFalse(fake_tts.calls[0]["split_sentences"])


if __name__ == "__main__":
    unittest.main()
