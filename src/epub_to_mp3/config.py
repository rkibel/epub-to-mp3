from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class VoiceConfig:
    english_voice: str = "af_heart"
    xtts_speaker_wav: Path | None = None
    xtts_temperature: float = 0.7
    xtts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"


@dataclass(slots=True)
class RoutingConfig:
    supported_languages: tuple[str, ...] = ("en", "es", "fr", "ru")
    chunk_size: int = 450
    minimum_span_length: int = 6


@dataclass(slots=True)
class AppConfig:
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
