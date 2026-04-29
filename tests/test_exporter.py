from __future__ import annotations

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from epub_to_mp3.audio import write_wav_file
from epub_to_mp3.exporter import _build_ffmetadata, export_chapter_wavs, export_wav_directory
from epub_to_mp3.tts.base import SynthesisResult


def _make_silence_wav(path: Path, sample_rate: int = 24000, duration_ms: int = 120) -> Path:
    frame_count = int(sample_rate * (duration_ms / 1000.0))
    samples = b"\x00\x00" * frame_count
    return write_wav_file(
        path,
        SynthesisResult(
            sample_rate=sample_rate,
            samples=samples,
            audio_format="pcm_s16le",
            channels=1,
            sample_width=2,
        ),
    )


class ExportMetadataTests(unittest.TestCase):
    def test_ffmetadata_contains_book_and_chapter_markers(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            chapter_one = _make_silence_wav(temp_dir / "001-chapter-1.wav", duration_ms=100)
            chapter_two = _make_silence_wav(temp_dir / "002-chapter-2.wav", duration_ms=150)

            metadata = _build_ffmetadata(
                book_title="Sample Novel",
                author="Example Author",
                chapter_paths=[chapter_one, chapter_two],
                chapter_titles=["Part 1", "Chapter 1"],
            )

        self.assertIn(";FFMETADATA1", metadata)
        self.assertIn("title=Sample Novel", metadata)
        self.assertIn("artist=Example Author", metadata)
        self.assertIn("START=0", metadata)
        self.assertIn("END=100", metadata)
        self.assertIn("START=100", metadata)
        self.assertIn("END=250", metadata)
        self.assertIn("title=Part 1", metadata)
        self.assertIn("title=Chapter 1", metadata)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for export integration tests")
class ExportIntegrationTests(unittest.TestCase):
    def test_export_chapter_wavs_creates_m4b(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            chapter_one = _make_silence_wav(temp_dir / "001-part-1.wav")
            chapter_two = _make_silence_wav(temp_dir / "002-chapter-1.wav")
            output_path = temp_dir / "sample-novel.m4b"

            exported = export_chapter_wavs(
                chapter_paths=[chapter_one, chapter_two],
                output_path=output_path,
                book_title="Sample Novel",
                author="Example Author",
                chapter_titles=["Part 1", "Chapter 1"],
            )

            self.assertEqual(exported, output_path)
            self.assertTrue(exported.exists())
            self.assertGreater(exported.stat().st_size, 0)

    def test_export_wav_directory_creates_mp3(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            _make_silence_wav(temp_dir / "001-part-1.wav")
            _make_silence_wav(temp_dir / "002-chapter-1.wav")

            exported = export_wav_directory(
                temp_dir,
                export_format="mp3",
                book_title="Sample Novel",
                author="Example Author",
            )

            self.assertEqual(exported.suffix, ".mp3")
            self.assertTrue(exported.exists())
            self.assertGreater(exported.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
