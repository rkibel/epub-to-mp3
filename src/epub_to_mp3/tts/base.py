from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SynthesisResult:
    sample_rate: int
    samples: bytes
    audio_format: str = "pcm_s16le"
    channels: int = 1
    sample_width: int = 2


class TTSBackend:
    language: str

    def synthesize(self, text: str) -> SynthesisResult:
        raise NotImplementedError
