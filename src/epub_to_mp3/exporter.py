from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import wave


SUPPORTED_EXPORT_FORMATS = ("m4b", "mp3")


def export_chapter_wavs(
    chapter_paths: list[str | Path],
    output_path: str | Path,
    *,
    book_title: str,
    author: str | None = None,
    chapter_titles: list[str] | None = None,
) -> Path:
    files = [Path(path) for path in chapter_paths]
    if not files:
        raise ValueError("No chapter WAV files were provided for export.")

    missing_files = [path for path in files if not path.exists()]
    if missing_files:
        missing_paths = ", ".join(str(path) for path in missing_files)
        raise FileNotFoundError(f"Missing chapter WAV files: {missing_paths}")

    output_file = Path(output_path)
    export_format = _infer_export_format(output_file)
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(
            "ffmpeg is required for MP3/M4B export but was not found on PATH. "
            "Install ffmpeg and run the export again."
        )

    resolved_chapter_titles = _resolve_chapter_titles(files, chapter_titles)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="epub-to-mp3-export-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        concat_manifest = temp_dir / "chapters.txt"
        ffmetadata_path = temp_dir / "metadata.ffmeta"

        concat_manifest.write_text(_build_concat_manifest(files), encoding="utf-8")
        ffmetadata_path.write_text(
            _build_ffmetadata(
                book_title=book_title,
                author=author,
                chapter_paths=files,
                chapter_titles=resolved_chapter_titles,
            ),
            encoding="utf-8",
        )

        command = _build_ffmpeg_command(
            ffmpeg_path=ffmpeg_path,
            concat_manifest=concat_manifest,
            ffmetadata_path=ffmetadata_path,
            output_path=output_file,
            export_format=export_format,
        )
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )

    if completed.returncode != 0:
        raise RuntimeError(_format_ffmpeg_failure(completed.stderr))

    return output_file


def export_wav_directory(
    input_dir: str | Path,
    *,
    output_path: str | Path | None = None,
    export_format: str = "m4b",
    book_title: str | None = None,
    author: str | None = None,
) -> Path:
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_path}")
    if not input_path.is_dir():
        raise NotADirectoryError(f"Expected a directory of chapter WAV files: {input_path}")

    chapter_paths = sorted(input_path.glob("*.wav"))
    if not chapter_paths:
        raise ValueError(f"No WAV files were found in {input_path}")

    resolved_title = book_title or _derive_book_title(input_path)
    resolved_output_path = _resolve_export_output_path(
        output_path=output_path,
        export_format=export_format,
        parent_dir=input_path,
        default_stem=_slugify(resolved_title),
    )

    return export_chapter_wavs(
        chapter_paths=[path for path in chapter_paths],
        output_path=resolved_output_path,
        book_title=resolved_title,
        author=author,
    )


def _infer_export_format(output_path: Path) -> str:
    export_format = output_path.suffix.lower().lstrip(".")
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        supported = ", ".join(SUPPORTED_EXPORT_FORMATS)
        raise ValueError(
            f"Unsupported export format '{export_format or '(missing extension)'}'. "
            f"Supported formats: {supported}."
        )
    return export_format


def _resolve_export_output_path(
    *,
    output_path: str | Path | None,
    export_format: str,
    parent_dir: Path,
    default_stem: str,
) -> Path:
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        supported = ", ".join(SUPPORTED_EXPORT_FORMATS)
        raise ValueError(f"Unsupported export format '{export_format}'. Supported formats: {supported}.")

    if output_path is None:
        return parent_dir / f"{default_stem}.{export_format}"

    resolved_output_path = Path(output_path)
    if resolved_output_path.suffix:
        return resolved_output_path
    return resolved_output_path.with_suffix(f".{export_format}")


def _resolve_chapter_titles(chapter_paths: list[Path], chapter_titles: list[str] | None) -> list[str]:
    if chapter_titles is None:
        return [_derive_chapter_title(path) for path in chapter_paths]

    if len(chapter_titles) != len(chapter_paths):
        raise ValueError("The number of chapter titles must match the number of chapter WAV files.")
    return chapter_titles


def _build_concat_manifest(chapter_paths: list[Path]) -> str:
    lines = [f"file '{_escape_concat_path(path.resolve())}'" for path in chapter_paths]
    return "\n".join(lines) + "\n"


def _build_ffmetadata(
    *,
    book_title: str,
    author: str | None,
    chapter_paths: list[Path],
    chapter_titles: list[str],
) -> str:
    lines = [";FFMETADATA1"]
    lines.append(f"title={_escape_ffmetadata_value(book_title)}")
    lines.append(f"album={_escape_ffmetadata_value(book_title)}")
    lines.append("genre=Audiobook")
    if author:
        escaped_author = _escape_ffmetadata_value(author)
        lines.append(f"artist={escaped_author}")
        lines.append(f"album_artist={escaped_author}")

    current_start_ms = 0
    for chapter_path, chapter_title in zip(chapter_paths, chapter_titles, strict=True):
        duration_ms = _read_wav_duration_ms(chapter_path)
        lines.extend(
            [
                "",
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={current_start_ms}",
                f"END={current_start_ms + duration_ms}",
                f"title={_escape_ffmetadata_value(chapter_title)}",
            ]
        )
        current_start_ms += duration_ms

    return "\n".join(lines) + "\n"


def _build_ffmpeg_command(
    *,
    ffmpeg_path: str,
    concat_manifest: Path,
    ffmetadata_path: Path,
    output_path: Path,
    export_format: str,
) -> list[str]:
    command = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_manifest),
        "-i",
        str(ffmetadata_path),
        "-map",
        "0:a:0",
        "-map_metadata",
        "1",
        "-map_chapters",
        "1",
        "-vn",
    ]

    if export_format == "mp3":
        command.extend(["-c:a", "libmp3lame", "-q:a", "2"])
    elif export_format == "m4b":
        command.extend(["-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-f", "mp4"])
    else:  # pragma: no cover - guarded by upfront validation
        raise ValueError(f"Unsupported export format: {export_format}")

    command.append(str(output_path))
    return command


def _format_ffmpeg_failure(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if not lines:
        return "ffmpeg failed to export the audiobook for an unknown reason."
    tail = "\n".join(lines[-8:])
    return f"ffmpeg failed to export the audiobook:\n{tail}"


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace("'", "\\'")


def _escape_ffmetadata_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace("#", "\\#")
        .replace("=", "\\=")
        .replace("\n", " ")
    )


def _read_wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        sample_rate = wav_file.getframerate()
    if sample_rate <= 0:
        raise ValueError(f"WAV file has an invalid sample rate: {path}")
    return max(1, round((frames / sample_rate) * 1000))


def _derive_book_title(input_dir: Path) -> str:
    raw_name = input_dir.name.replace("_", " ").replace("-", " ").strip()
    return raw_name.title() or "Audiobook"


def _derive_chapter_title(path: Path) -> str:
    stem = re.sub(r"^\d+-", "", path.stem).replace("_", " ").replace("-", " ").strip()
    return stem.title() or path.stem


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "audiobook"
