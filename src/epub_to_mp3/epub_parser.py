from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from epub_to_mp3.models import Book, Chapter


CONTAINER_NS = {"ct": "urn:oasis:names:tc:opendocument:xmlns:container"}
OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def parse_epub(path: str | Path) -> Book:
    epub_path = Path(path)
    if epub_path.is_dir():
        return _parse_exploded_epub(epub_path)
    return _parse_packaged_epub(epub_path)


def _parse_exploded_epub(epub_dir: Path) -> Book:
    opf_path = _find_opf_path(epub_dir)
    opf_root = ET.parse(opf_path).getroot()

    title = _find_text(opf_root, "opf:metadata/dc:title") or epub_dir.stem
    author = _find_text(opf_root, "opf:metadata/dc:creator")
    manifest = _read_manifest(opf_root)
    chapters: list[Chapter] = []

    spine = opf_root.find("opf:spine", OPF_NS)
    if spine is None:
        raise RuntimeError(f"Exploded EPUB is missing an OPF spine: {opf_path}")

    for itemref in spine.findall("opf:itemref", OPF_NS):
        item_id = itemref.attrib.get("idref", "")
        href = manifest.get(item_id)
        if not href:
            continue

        document_path = opf_path.parent / href
        if not document_path.exists():
            continue

        html = document_path.read_text(encoding="utf-8", errors="replace")
        text = _html_to_text(html)
        if not text.strip():
            continue
        if _should_skip_document(item_id=item_id, file_name=href, text=text, html=html):
            continue

        chapter_number = len(chapters) + 1
        chapters.append(
            Chapter(
                index=chapter_number,
                title=_extract_title(html, fallback=f"Chapter {chapter_number}"),
                text=text,
            )
        )

    return Book(title=title, author=author, chapters=chapters)


def _parse_packaged_epub(epub_path: Path) -> Book:
    try:
        from ebooklib import ITEM_DOCUMENT, epub
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Packaged EPUB parsing requires `ebooklib`. Install project dependencies or provide an exploded EPUB directory."
        ) from exc

    book = epub.read_epub(str(epub_path))
    title = _read_metadata(book, "title") or epub_path.stem
    author = _read_metadata(book, "creator")
    chapters: list[Chapter] = []

    for item in _iter_spine_documents(book, item_document_type=ITEM_DOCUMENT):
        html = item.get_body_content().decode("utf-8", errors="replace")
        text = _html_to_text(html)
        if not text.strip():
            continue
        if _should_skip_document(
            item_id=str(getattr(item, "id", "") or ""),
            file_name=str(getattr(item, "file_name", "") or ""),
            text=text,
            html=html,
        ):
            continue

        chapter_number = len(chapters) + 1
        chapters.append(
            Chapter(
                index=chapter_number,
                title=_extract_title(html, fallback=f"Chapter {chapter_number}"),
                text=text,
            )
        )

    return Book(title=title, author=author, chapters=chapters)


def _find_opf_path(epub_dir: Path) -> Path:
    container_path = epub_dir / "META-INF" / "container.xml"
    if not container_path.exists():
        raise RuntimeError(f"Exploded EPUB is missing META-INF/container.xml: {epub_dir}")

    container_root = ET.parse(container_path).getroot()
    rootfile = container_root.find("ct:rootfiles/ct:rootfile", CONTAINER_NS)
    if rootfile is None:
        raise RuntimeError(f"Could not locate a rootfile in {container_path}")

    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise RuntimeError(f"Rootfile entry in {container_path} is missing `full-path`")

    opf_path = epub_dir / full_path
    if not opf_path.exists():
        raise RuntimeError(f"OPF path declared in {container_path} does not exist: {opf_path}")
    return opf_path


def _read_manifest(opf_root: ET.Element) -> dict[str, str]:
    manifest = opf_root.find("opf:manifest", OPF_NS)
    if manifest is None:
        raise RuntimeError("Exploded EPUB is missing an OPF manifest.")

    mapping: dict[str, str] = {}
    for item in manifest.findall("opf:item", OPF_NS):
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        if item_id and href:
            mapping[item_id] = href
    return mapping


def _find_text(root: ET.Element, path: str) -> str | None:
    node = root.find(path, OPF_NS)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _html_to_text(html: str) -> str:
    extractor = _HTMLSummaryParser()
    extractor.feed(html)
    extractor.close()
    return _normalize_whitespace(" ".join(extractor.text_parts))


def _extract_title(html: str, fallback: str) -> str:
    extractor = _HTMLSummaryParser()
    extractor.feed(html)
    extractor.close()

    for key in ("h1", "h2", "h3", "title"):
        value = extractor.first_text_by_tag.get(key)
        if value:
            return value
    return fallback


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _read_metadata(book: Any, key: str) -> str | None:
    values = book.get_metadata("DC", key)
    if not values:
        return None
    return str(values[0][0]).strip() or None


def _iter_spine_documents(book: Any, item_document_type: int):
    seen_ids: set[str] = set()
    yielded_any = False
    for spine_entry in getattr(book, "spine", []):
        item_id = spine_entry[0] if isinstance(spine_entry, tuple) else spine_entry
        if not isinstance(item_id, str) or item_id == "nav" or item_id in seen_ids:
            continue

        item = book.get_item_with_id(item_id)
        if item is None or item.get_type() != item_document_type:
            continue

        seen_ids.add(item_id)
        yielded_any = True
        yield item

    if yielded_any:
        return

    for item in book.get_items_of_type(item_document_type):
        item_id = (getattr(item, "id", None) or getattr(item, "get_id", lambda: None)()) or ""
        if item_id in seen_ids:
            continue
        seen_ids.add(str(item_id))
        yield item


def _should_skip_document(item_id: str, file_name: str, text: str, html: str) -> bool:
    normalized_id = item_id.lower()
    file_stem = Path(file_name.lower()).stem
    lowered_text = text.lower()
    document_title = (_extract_document_title(html) or "").lower()
    normalized_title = document_title.replace("-", " ").replace("_", " ").strip()
    lowered_html = html.lower()

    if normalized_id in {"nav", "toc", "contents"}:
        return True
    if file_stem in {"nav", "toc", "contents", "table-of-contents", "table_of_contents"}:
        return True
    if len(text) < 120 and ("table of contents" in lowered_text or "contents" == lowered_text.strip()):
        return True
    if normalized_title in {"cover", "title page", "footnotes", "foonotes", "contents", "table of contents"}:
        return True
    if '<div class="footnote"' in lowered_html:
        return True
    return False


def _extract_document_title(html: str) -> str | None:
    extractor = _HTMLSummaryParser()
    extractor.feed(html)
    extractor.close()
    return extractor.first_text_by_tag.get("title")


class _HTMLSummaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.first_text_by_tag: dict[str, str] = {}
        self.text_parts: list[str] = []
        self._tag_stack: list[str] = []
        self._tag_buffers: dict[str, list[str]] = {"title": [], "h1": [], "h2": [], "h3": []}
        self._inside_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        if tag == "body":
            self._inside_body = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._tag_buffers and tag not in self.first_text_by_tag:
            text = _normalize_whitespace(" ".join(self._tag_buffers[tag]))
            if text:
                self.first_text_by_tag[tag] = text

        if tag == "body":
            self._inside_body = False

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
            return

        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == tag:
                del self._tag_stack[index]
                return

    def handle_data(self, data: str) -> None:
        text = _normalize_whitespace(data)
        if not text:
            return

        if self._inside_body:
            self.text_parts.append(text)
        for tag in self._tag_stack:
            if tag in self._tag_buffers and tag not in self.first_text_by_tag:
                self._tag_buffers[tag].append(text)
