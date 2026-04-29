from __future__ import annotations

from pathlib import Path
from typing import Any

from epub_to_mp3.audio import float_audio_to_pcm16
from epub_to_mp3.tts.base import SynthesisResult, TTSBackend


class XTTSBackend(TTSBackend):
    def __init__(self, language: str, speaker_wav: Path | None, model_name: str) -> None:
        self.language = language
        self.speaker_wav = speaker_wav
        self.model_name = model_name
        self._tts: Any | None = None

    def synthesize(self, text: str) -> SynthesisResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Cannot synthesize empty text with XTTS.")
        if self.speaker_wav is None:
            raise RuntimeError(
                "XTTS requires a reference speaker WAV. Provide `xtts_speaker_wav` or allow the factory "
                "to generate one from Kokoro."
            )

        tts = self._get_tts()
        try:
            wav = tts.tts(
                text=normalized_text,
                speaker_wav=[str(self.speaker_wav)],
                language=self.language,
                split_sentences=False,
            )
        except TypeError:
            wav = tts.tts(
                text=normalized_text,
                speaker_wav=str(self.speaker_wav),
                language=self.language,
                split_sentences=False,
            )

        return SynthesisResult(
            sample_rate=24000,
            samples=float_audio_to_pcm16(wav),
            audio_format="pcm_s16le",
            channels=1,
            sample_width=2,
        )

    def _get_tts(self) -> Any:
        if self._tts is not None:
            return self._tts

        try:
            import importlib
            import torch
            import transformers
            from transformers.generation.beam_search import BeamSearchScorer
            from transformers.generation.utils import GenerationMixin
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "XTTS dependencies are not installed. Install the `TTS` package to enable multilingual synthesis."
            ) from exc

        if not hasattr(transformers, "BeamSearchScorer"):
            transformers.BeamSearchScorer = BeamSearchScorer
            transformers.__dict__["BeamSearchScorer"] = BeamSearchScorer
            exported = list(getattr(transformers, "__all__", []))
            if "BeamSearchScorer" not in exported:
                exported.append("BeamSearchScorer")
                transformers.__all__ = exported

        gpt_inference = importlib.import_module("TTS.tts.layers.xtts.gpt_inference")
        if not hasattr(gpt_inference.GPT2InferenceModel, "generate"):
            gpt_inference.GPT2InferenceModel.generate = GenerationMixin.generate

        importlib.import_module("TTS.tts.layers.xtts.stream_generator")

        try:
            from TTS.api import TTS
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "XTTS dependencies are not installed. Install the `TTS` package to enable multilingual synthesis."
            ) from exc

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        try:
            original_torch_load = torch.load

            def _compat_torch_load(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return original_torch_load(*args, **kwargs)

            torch.load = _compat_torch_load
            self._tts = TTS(self.model_name).to(device)
        except EOFError as exc:
            raise RuntimeError(
                "XTTS requires a one-time interactive acceptance of the Coqui model license before the model can "
                "be downloaded. Run the XTTS loader once in an interactive terminal and answer the license prompt."
            ) from exc
        finally:
            torch.load = original_torch_load
        return self._tts
