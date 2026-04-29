from __future__ import annotations

import wave
from pathlib import Path

from epub_to_mp3.config import AppConfig
from epub_to_mp3.tts.base import TTSBackend
from epub_to_mp3.tts.kokoro import KokoroBackend
from epub_to_mp3.tts.xtts import XTTSBackend


def build_tts_registry(config: AppConfig) -> dict[str, TTSBackend]:
    english_backend = KokoroBackend(voice=config.voice.english_voice)
    xtts_speaker_wav = config.voice.xtts_speaker_wav or _ensure_xtts_reference_wav(english_backend)

    return {
        "en": english_backend,
        "es": XTTSBackend(
            language="es",
            speaker_wav=xtts_speaker_wav,
            model_name=config.voice.xtts_model_name,
        ),
        "fr": XTTSBackend(
            language="fr",
            speaker_wav=xtts_speaker_wav,
            model_name=config.voice.xtts_model_name,
        ),
        "ru": XTTSBackend(
            language="ru",
            speaker_wav=xtts_speaker_wav,
            model_name=config.voice.xtts_model_name,
        ),
    }


def _ensure_xtts_reference_wav(english_backend: KokoroBackend) -> Path | None:
    try:
        result = english_backend.synthesize(
            "This is a multilingual voice reference for the audiobook conversion pipeline."
        )
    except Exception:
        return None

    reference_dir = Path(".tts-cache")
    reference_dir.mkdir(parents=True, exist_ok=True)
    reference_path = reference_dir / f"xtts-reference-{english_backend.voice}.wav"
    with wave.open(str(reference_path), "wb") as wav_file:
        wav_file.setnchannels(result.channels)
        wav_file.setsampwidth(result.sample_width)
        wav_file.setframerate(result.sample_rate)
        wav_file.writeframes(result.samples)
    return reference_path
