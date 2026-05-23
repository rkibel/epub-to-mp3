# Chapter preview queue for audiobook conversion

This Forge-generated MVP adds a preflight chapter queue demo for the EPUB-to-audio workflow.
It is intentionally repo-contained so it can be reviewed without paid APIs, TTS downloads, or production deployment.

## Product MVP

Add a lightweight preflight/preview experience that shows a chapter queue, detected language spans, selected export format, and smoke-testable sample data before full TTS conversion. For the demo PR, implement this as a small repo-contained MVP surface with README instructions and smoke checks.

## Run

```bash
python chapter_preview_queue_for_audiobook_conversion_demo.py sample_chapters.json
```

## Smoke checks

```bash
python -m unittest chapter_preview_queue_for_audiobook_conversion_demo_test.py -v
```

## Services

No external services are required. This demo uses local Python standard-library code only.

## Notes

The MVP previews chapter order, detected language, export format, and estimated output before full synthesis.