from __future__ import annotations

from pathlib import Path
import wave

from epub_to_mp3.tts.base import SynthesisResult


def float_audio_to_pcm16(samples: list[float]) -> bytes:
    pcm = bytearray()
    for sample in samples:
        clipped = max(-1.0, min(1.0, float(sample)))
        scaled = int(clipped * 32767.0)
        pcm.extend(scaled.to_bytes(2, byteorder="little", signed=True))
    return bytes(pcm)


def concat_synthesis_results(
    results: list[SynthesisResult],
    silence_ms: int = 0,
) -> SynthesisResult | None:
    return concat_synthesis_results_with_gaps(
        [(result, silence_ms if index else 0) for index, result in enumerate(results)]
    )


def concat_synthesis_results_with_gaps(
    results: list[tuple[SynthesisResult, int]],
) -> SynthesisResult | None:
    if not results:
        return None

    first_result = results[0][0]
    _validate_pcm16_result(first_result)
    sample_rate = first_result.sample_rate
    audio_format = first_result.audio_format
    channels = first_result.channels
    sample_width = first_result.sample_width

    combined = bytearray()
    for index, (result, leading_silence_ms) in enumerate(results):
        _validate_pcm16_result(result)
        if result.sample_rate != sample_rate:
            raise ValueError("Cannot concatenate audio with mixed sample rates.")
        if result.audio_format != audio_format:
            raise ValueError("Cannot concatenate audio with mixed audio formats.")
        if result.channels != channels or result.sample_width != sample_width:
            raise ValueError("Cannot concatenate audio with mixed channel layouts.")
        if index:
            silence_frames = max(0, int(sample_rate * (leading_silence_ms / 1000.0)))
            silence = b"\x00" * (silence_frames * channels * sample_width)
            combined.extend(silence)
        combined.extend(_trim_boundary_silence(result).samples)

    return SynthesisResult(
        sample_rate=sample_rate,
        samples=bytes(combined),
        audio_format=audio_format,
        channels=channels,
        sample_width=sample_width,
    )


def write_wav_file(path: Path, audio: SynthesisResult) -> Path:
    _validate_pcm16_result(audio)

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(audio.channels)
        wav_file.setsampwidth(audio.sample_width)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(audio.samples)
    return path


def _validate_pcm16_result(audio: SynthesisResult) -> None:
    if audio.audio_format != "pcm_s16le":
        raise ValueError(f"Unsupported audio format for PCM concatenation/WAV export: {audio.audio_format}")
    if audio.sample_width != 2:
        raise ValueError(f"Unsupported sample width for PCM16 audio: {audio.sample_width}")
    frame_width = audio.channels * audio.sample_width
    if frame_width <= 0:
        raise ValueError("Audio frame width must be positive.")
    if len(audio.samples) % frame_width != 0:
        raise ValueError("Audio byte length does not align with the declared channel/sample width metadata.")


def _trim_boundary_silence(
    audio: SynthesisResult,
    *,
    threshold: int = 96,
    keep_leading_ms: int = 40,
    keep_trailing_ms: int = 80,
) -> SynthesisResult:
    _validate_pcm16_result(audio)

    frame_width = audio.channels * audio.sample_width
    frame_count = len(audio.samples) // frame_width
    if frame_count == 0:
        return audio

    first_sound_frame = 0
    while first_sound_frame < frame_count and _is_silent_frame(audio.samples, first_sound_frame, frame_width, threshold):
        first_sound_frame += 1

    if first_sound_frame == frame_count:
        return audio

    last_sound_frame = frame_count - 1
    while last_sound_frame > first_sound_frame and _is_silent_frame(
        audio.samples, last_sound_frame, frame_width, threshold
    ):
        last_sound_frame -= 1
    last_sound_frame = _discard_trailing_orphan_sound(
        samples=audio.samples,
        sample_rate=audio.sample_rate,
        frame_width=frame_width,
        first_sound_frame=first_sound_frame,
        last_sound_frame=last_sound_frame,
        threshold=threshold,
    )

    keep_leading_frames = int(audio.sample_rate * (keep_leading_ms / 1000.0))
    keep_trailing_frames = int(audio.sample_rate * (keep_trailing_ms / 1000.0))
    start_frame = max(0, first_sound_frame - keep_leading_frames)
    end_frame = min(frame_count, last_sound_frame + 1 + keep_trailing_frames)

    if start_frame == 0 and end_frame == frame_count:
        return audio

    return SynthesisResult(
        sample_rate=audio.sample_rate,
        samples=audio.samples[start_frame * frame_width : end_frame * frame_width],
        audio_format=audio.audio_format,
        channels=audio.channels,
        sample_width=audio.sample_width,
    )


def _is_silent_frame(samples: bytes, frame_index: int, frame_width: int, threshold: int) -> bool:
    frame_start = frame_index * frame_width
    for sample_start in range(frame_start, frame_start + frame_width, 2):
        sample = int.from_bytes(samples[sample_start : sample_start + 2], byteorder="little", signed=True)
        if abs(sample) > threshold:
            return False
    return True


def _discard_trailing_orphan_sound(
    *,
    samples: bytes,
    sample_rate: int,
    frame_width: int,
    first_sound_frame: int,
    last_sound_frame: int,
    threshold: int,
    window_ms: int = 10,
    silence_gap_ms: int = 300,
    max_orphan_ms: int = 120,
) -> int:
    window_frames = max(1, int(sample_rate * (window_ms / 1000.0)))
    first_window = first_sound_frame // window_frames
    last_window = last_sound_frame // window_frames

    active_windows: dict[int, bool] = {}
    for window_index in range(first_window, last_window + 1):
        window_start = window_index * window_frames
        window_end = min(last_sound_frame + 1, window_start + window_frames)
        active_windows[window_index] = any(
            not _is_silent_frame(samples, frame_index, frame_width, threshold)
            for frame_index in range(window_start, window_end)
        )

    final_start_window = last_window
    while final_start_window > first_window and active_windows.get(final_start_window - 1, False):
        final_start_window -= 1

    final_cluster_ms = ((last_window - final_start_window + 1) * window_frames / sample_rate) * 1000.0
    if final_cluster_ms > max_orphan_ms:
        return last_sound_frame

    silence_windows = 0
    probe_window = final_start_window - 1
    while probe_window >= first_window and not active_windows.get(probe_window, False):
        silence_windows += 1
        probe_window -= 1

    silence_gap = (silence_windows * window_frames / sample_rate) * 1000.0
    if probe_window >= first_window and silence_gap >= silence_gap_ms:
        previous_window_end = min(last_sound_frame, (probe_window + 1) * window_frames - 1)
        while previous_window_end > first_sound_frame and _is_silent_frame(
            samples, previous_window_end, frame_width, threshold
        ):
            previous_window_end -= 1
        return previous_window_end

    return last_sound_frame
