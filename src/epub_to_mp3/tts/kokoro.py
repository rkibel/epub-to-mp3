from __future__ import annotations

from collections.abc import Iterable, Sequence
from importlib import import_module
from typing import Any

from epub_to_mp3.tts.base import SynthesisResult, TTSBackend


class KokoroBackend(TTSBackend):
    language = "en"

    def __init__(self, voice: str) -> None:
        self.voice = voice
        self._pipeline: Any | None = None

    def synthesize(self, text: str) -> SynthesisResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Cannot synthesize empty text with Kokoro.")

        pipeline = self._get_pipeline()
        try:
            segments = pipeline(normalized_text, voice=self.voice, speed=1.0)
        except TypeError as exc:
            raise RuntimeError(
                "Installed Kokoro pipeline did not accept the expected call signature "
                "`pipeline(text, voice=..., speed=...)`. Adjust the adapter in "
                "`src/epub_to_mp3/tts/kokoro.py` for the installed Kokoro package version."
            ) from exc

        pcm_frames = bytearray()
        sample_rate: int | None = None
        segment_count = 0

        for segment in segments:
            audio_payload = self._extract_audio_payload(segment)
            rate, frames = self._segment_to_pcm16(audio_payload)
            if sample_rate is None:
                sample_rate = rate
            elif sample_rate != rate:
                raise RuntimeError(
                    "Kokoro returned segments with inconsistent sample rates, which cannot be stitched safely."
                )
            pcm_frames.extend(frames)
            segment_count += 1

        if segment_count == 0 or sample_rate is None:
            raise RuntimeError("Kokoro returned no audio for the requested text.")

        return SynthesisResult(
            sample_rate=sample_rate,
            samples=bytes(pcm_frames),
            audio_format="pcm_s16le",
            channels=1,
            sample_width=2,
        )

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        try:
            kokoro_module = import_module("kokoro")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Kokoro dependencies are not installed. Install a Kokoro package that exposes "
                "`kokoro.KPipeline` plus its runtime dependencies (typically including torch)."
            ) from exc

        pipeline_cls = getattr(kokoro_module, "KPipeline", None)
        if pipeline_cls is None:
            raise RuntimeError(
                "Installed `kokoro` package does not expose `KPipeline`. This backend currently "
                "targets the Hugging Face Kokoro Python API that provides `kokoro.KPipeline`."
            )

        try:
            self._pipeline = pipeline_cls(lang_code=self._infer_lang_code())
        except TypeError as exc:
            raise RuntimeError(
                "Failed to initialize `kokoro.KPipeline(lang_code=...)`. The installed Kokoro API "
                "looks different from the adapter this project expects."
            ) from exc

        return self._pipeline

    def _infer_lang_code(self) -> str:
        # Kokoro English voices are typically prefixed with `a` (American) or `b` (British).
        # If the voice does not follow that convention we default to American English.
        voice_prefix = self.voice[:1].lower()
        return voice_prefix if voice_prefix in {"a", "b"} else "a"

    def _extract_audio_payload(self, segment: Any) -> Any:
        if isinstance(segment, tuple):
            if not segment:
                raise RuntimeError("Kokoro returned an empty tuple segment.")
            return segment[-1]
        if not isinstance(segment, (str, bytes)) and hasattr(segment, "__len__") and hasattr(segment, "__getitem__"):
            if len(segment) == 0:
                raise RuntimeError("Kokoro returned an empty segment.")
            return segment[-1]
        return segment

    def _segment_to_pcm16(self, audio_payload: Any) -> tuple[int, bytes]:
        if isinstance(audio_payload, bytes):
            raise RuntimeError(
                "Kokoro backend returned raw bytes for a segment, but this adapter only knows how "
                "to normalize numeric sample arrays. Extend `KokoroBackend` for this package variant."
            )

        sample_rate_value = getattr(audio_payload, "sample_rate", None)
        # The upstream Kokoro examples write the returned waveform at 24000 Hz when the
        # generator yields a plain array without embedded rate metadata.
        sample_rate = int(sample_rate_value) if sample_rate_value is not None else 24000
        sample_values = self._coerce_sample_values(audio_payload)
        return sample_rate, self._float_samples_to_pcm16(sample_values)

    def _coerce_sample_values(self, audio_payload: Any) -> list[float]:
        candidate = audio_payload

        for method_name in ("detach", "cpu", "float"):
            method = getattr(candidate, method_name, None)
            if callable(method):
                candidate = method()

        if hasattr(candidate, "numpy") and callable(candidate.numpy):
            candidate = candidate.numpy()

        if hasattr(candidate, "tolist") and callable(candidate.tolist):
            values = candidate.tolist()
        elif isinstance(candidate, Sequence):
            values = list(candidate)
        elif isinstance(candidate, Iterable):
            values = list(candidate)
        else:
            raise RuntimeError(
                "Kokoro returned audio in an unsupported container type. Expected a tensor/array/list-like value."
            )

        if values and isinstance(values[0], list):
            raise RuntimeError(
                "Kokoro returned multi-channel audio data. This adapter currently expects a mono waveform."
            )

        try:
            return [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Kokoro returned non-numeric audio samples.") from exc

    def _float_samples_to_pcm16(self, samples: Sequence[float]) -> bytes:
        pcm = bytearray()
        for sample in samples:
            clipped = max(-1.0, min(1.0, sample))
            scaled = int(clipped * 32767.0)
            pcm.extend(scaled.to_bytes(2, byteorder="little", signed=True))
        return bytes(pcm)
