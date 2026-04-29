# epub-to-mp3

Convert EPUB books into audiobook audio with a hybrid Kokoro + XTTS v2 pipeline and automatic English, Spanish, French, and Russian language routing.

## Status

The current codebase can:

- Parse packaged `.epub` files and exploded EPUB directories
- Split chapter text into sentence-aware routing chunks
- Detect and route English, Spanish, French, and Russian spans
- Synthesize chapter audio through Kokoro for English and XTTS v2 for Spanish, French, and Russian
- Write per-chapter `.wav` files
- Export rendered chapter WAVs into a single `.mp3` or chapter-marked `.m4b` listening file with `ffmpeg`

The repository name still says "mp3", but the pipeline now uses WAV as an intermediate render format and can optionally package the result as MP3 or M4B.

## What The Formats Mean

- `EPUB` is the input ebook container. It holds book text, metadata, images, and navigation.
- `WAV` is the intermediate chapter audio format. It is uncompressed and easy to generate, but the files are large.
- `MP3` is a smaller, broadly compatible listening format.
- `M4B` is an audiobook-friendly Apple format that can hold chapters and works well for iPhone listening.

If your goal is "drop an EPUB into the repo, generate audio, and listen on iPhone," the current flow is:

1. Add the EPUB locally.
2. Run `convert` with `--export-format m4b`.
3. Put the resulting `.m4b` file into iCloud Drive.
4. Open it on your iPhone from the Files app or another audiobook-capable player.

That is the best current path for a single easier-listening file from this repo.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
brew install ffmpeg
epub-to-mp3 inspect path/to/book.epub
```

The first XTTS run may download model files and can require an interactive acceptance of the Coqui model license.

## CLI

Inspect parsing and language routing:

```bash
epub-to-mp3 inspect path/to/book.epub --max-chapters 2
```

Inspect a full book with custom routing:

```bash
epub-to-mp3 inspect path/to/book.epub --max-chapters 2 --chunk-size 120
```

Convert an EPUB into chapter WAV files:

```bash
epub-to-mp3 convert path/to/book.epub --output-dir output/book-audio
```

Convert and immediately package a single listening file:

```bash
epub-to-mp3 convert path/to/book.epub --output-dir output/book-audio --export-format m4b
```

Convert with custom routing and export:

```bash
epub-to-mp3 convert path/to/book.epub --output-dir output/book-audio --chunk-size 120 --export-format m4b
```

Export an existing WAV directory without rerunning TTS:

```bash
epub-to-mp3 export output/book-audio --format m4b --title "Book Title" --author "Author Name"
```

## Chunk Tuning

Routing happens before synthesis. The router first detects language at sentence boundaries, then groups adjacent sentences with the same language until `--chunk-size` is reached.

- Smaller `--chunk-size` values keep synthesis requests shorter.
- Larger `--chunk-size` values are faster and produce fewer spans.

Reasonable starting points:

- `--chunk-size 450`: current default, good for longer monolingual stretches
- `--chunk-size 180`: balanced starting point for books with occasional French or Spanish inserts
- `--chunk-size 120`: useful for debugging shorter synthesis spans

## Example

```bash
epub-to-mp3 inspect path/to/book.epub --max-chapters 2 --chunk-size 180
epub-to-mp3 convert path/to/book.epub --output-dir output/book-audio --chunk-size 180 --export-format m4b
```

That produces:

- Chapter WAV files in `output/book-audio/`
- A single listening file in `output/book-audio/`

If you want a lighter-weight file for broader compatibility instead, use `--export-format mp3`.

## Tests

Run the test suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test*.py' -v
```
