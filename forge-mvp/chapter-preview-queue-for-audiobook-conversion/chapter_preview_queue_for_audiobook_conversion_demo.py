"""Preflight chapter queue demo for epub-to-mp3."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def build_preview(payload: dict) -> dict:
    chapters = payload.get("chapters", [])
    total_minutes = sum(float(chapter.get("estimated_minutes", 0)) for chapter in chapters)
    languages = sorted({chapter.get("language", "unknown") for chapter in chapters})
    return {
        "book": payload.get("book", "Untitled EPUB"),
        "export_format": payload.get("export_format", "m4b"),
        "chapter_count": len(chapters),
        "languages": languages,
        "estimated_minutes": round(total_minutes, 1),
        "queue": [
            {
                "index": chapter.get("index"),
                "title": chapter.get("title", "Untitled chapter"),
                "language": chapter.get("language", "unknown"),
                "status": "ready_for_synthesis",
            }
            for chapter in chapters
        ],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python preflight_demo.py sample_chapters.json", file=sys.stderr)
        return 2
    payload = json.loads(Path(argv[1]).read_text())
    print(json.dumps(build_preview(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))