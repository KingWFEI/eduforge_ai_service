import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MARKDOWN_EXTENSIONS = {".md", ".markdown"}
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUMBERED_HEADING_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<title>\S.{0,119})$"
)
_PAGE_NO_RE = re.compile(r"^\s*(?:第\s*)?\d+\s*(?:页|/\s*\d+)?\s*$")
_REPEATED_NOISE_PATTERNS = (
    re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE),
    re.compile(r"^\s*[\w .-]+直播间[:：].*$", re.IGNORECASE),
)


@dataclass(frozen=True)
class MarkdownSection:
    title: str
    level: int
    heading_path: tuple[str, ...]
    content: str


@dataclass(frozen=True)
class StructuredChunk:
    content: str
    section: str
    heading_path: tuple[str, ...]
    heading_title: str | None
    heading_level: int | None


def convert_file_to_markdown(file_path: str) -> str:
    """Convert a supported document to Markdown using MarkItDown."""

    path = Path(file_path)
    if path.suffix.lower() in MARKDOWN_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".pdf":
        return _convert_pdf_with_page_markers(path)

    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError(
            "MarkItDown is not installed in the service interpreter. "
            "Run: python -m pip install 'markitdown[all]'"
        ) from exc

    result = MarkItDown(enable_plugins=False).convert(str(path))
    markdown = getattr(result, "text_content", None) or getattr(result, "markdown", None)
    return str(markdown or "")


def _convert_pdf_with_page_markers(path: Path) -> str:
    """Use MarkItDown's PDF dependency while preserving page boundaries."""

    import pdfplumber

    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            content = (page.extract_text() or "").strip()
            parts.append(f"<!-- Page number: {page_no} -->\n\n{content}")
    return "\n\n".join(parts).strip()


def clean_markdown(markdown: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    lines = [line.rstrip() for line in text.splitlines()]

    repeated_lines: dict[str, int] = {}
    for line in lines:
        normalized = _normalize_line(line)
        if 8 <= len(normalized) <= 160:
            repeated_lines[normalized] = repeated_lines.get(normalized, 0) + 1

    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        normalized = _normalize_line(line)
        if _PAGE_NO_RE.match(stripped):
            continue
        if any(pattern.match(stripped) for pattern in _REPEATED_NOISE_PATTERNS):
            continue
        if (
            repeated_lines.get(normalized, 0) >= 3
            and ("http://" in stripped or "https://" in stripped or "直播间" in stripped)
        ):
            continue
        if not stripped:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def normalize_markdown_headings(markdown: str) -> str:
    """Promote numbered plain-text headings and discard a duplicated leading TOC."""

    cleaned = clean_markdown(markdown)
    lines = cleaned.splitlines()
    toc_indexes = _leading_toc_heading_indexes(lines)
    normalized: list[str] = []

    for index, line in enumerate(lines):
        if index in toc_indexes:
            continue
        match = _NUMBERED_HEADING_RE.match(line.strip())
        if match:
            number = match.group("number")
            level = min(number.count(".") + 1, 6)
            normalized.append(f"{'#' * level} {line.strip()}")
        else:
            normalized.append(line)

    return "\n".join(normalized).strip()


def parse_markdown_sections(markdown: str) -> list[MarkdownSection]:
    normalized = normalize_markdown_headings(markdown)
    outline_by_number = {
        match.group("number"): title
        for _, title in extract_markdown_outline(markdown)
        if (match := _NUMBERED_HEADING_RE.match(title))
    }
    sections: list[MarkdownSection] = []
    heading_stack: list[tuple[int, str]] = []
    current_title: str | None = None
    current_level = 1
    current_path: tuple[str, ...] = ()
    content_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(content_lines).strip()
        if current_title and content:
            sections.append(
                MarkdownSection(
                    title=current_title,
                    level=current_level,
                    heading_path=current_path,
                    content=content,
                )
            )

    for line in normalized.splitlines():
        match = _MARKDOWN_HEADING_RE.match(line)
        if not match or not _is_probable_heading(match.group(2)):
            content_lines.append(line)
            continue

        flush()
        content_lines = []
        current_level = len(match.group(1))
        current_title = match.group(2).strip()
        numbered_match = _NUMBERED_HEADING_RE.match(current_title)
        if numbered_match:
            number = numbered_match.group("number")
            number_parts = number.split(".")
            prefixes = [".".join(number_parts[:index]) for index in range(1, len(number_parts) + 1)]
            heading_stack = [
                (
                    level,
                    current_title if prefix == number else outline_by_number[prefix],
                )
                for level, prefix in enumerate(prefixes, start=1)
                if prefix in outline_by_number or prefix == number
            ]
        else:
            while heading_stack and heading_stack[-1][0] >= current_level:
                heading_stack.pop()
            heading_stack.append((current_level, current_title))
        current_path = tuple(title for _, title in heading_stack)

    flush()

    if sections:
        return sections

    content = normalized.strip()
    return [
        MarkdownSection(
            title="文档正文",
            level=1,
            heading_path=("文档正文",),
            content=content,
        )
    ] if content else []


def extract_markdown_outline(markdown: str) -> list[tuple[int, str]]:
    cleaned_lines = clean_markdown(markdown).splitlines()
    toc_entries, _ = _leading_toc_entries(cleaned_lines)
    if toc_entries:
        return [
            (min(number.count(".") + 1, 6), _clean_numbered_heading(number, title))
            for _, number, title in toc_entries
        ]

    outline: list[tuple[int, str]] = []
    for line in normalize_markdown_headings(markdown).splitlines():
        match = _MARKDOWN_HEADING_RE.match(line)
        if match and _is_probable_heading(match.group(2)):
            outline.append((len(match.group(1)), match.group(2).strip()))
    return outline


def build_structure_context(markdown: str, max_chars: int = 22000) -> str:
    """Build deterministic outline-first input for course structure generation."""

    outline = extract_markdown_outline(markdown)
    sections = parse_markdown_sections(markdown)
    if not outline:
        return clean_markdown(markdown)[:max_chars]

    parts = ["【文档完整目录】"]
    for level, title in outline:
        parts.append(f"{'  ' * max(level - 1, 0)}- {title}")

    parts.append("\n【各小节正文摘要】")
    remaining = max_chars - sum(len(part) + 1 for part in parts)
    if remaining <= 0:
        return "\n".join(parts)[:max_chars]

    excerpt_size = max(180, min(500, remaining // max(len(sections), 1)))
    for section in sections:
        excerpt = re.sub(r"\s+", " ", section.content).strip()[:excerpt_size]
        block = f"\n小节：{' > '.join(section.heading_path)}\n摘要：{excerpt}"
        if sum(len(part) + 1 for part in parts) + len(block) > max_chars:
            break
        parts.append(block)
    return "\n".join(parts)[:max_chars]


def split_markdown_into_chunks(
    markdown: str,
    chunk_size: int = 1200,
    overlap: int = 120,
) -> list[StructuredChunk]:
    chunks: list[StructuredChunk] = []
    for section in parse_markdown_sections(markdown):
        for content in _split_section_content(section.content, chunk_size, overlap):
            heading = " > ".join(section.heading_path)
            chunk_content = f"{'#' * section.level} {section.title}\n\n{content}".strip()
            chunks.append(
                StructuredChunk(
                    content=chunk_content,
                    section=heading,
                    heading_path=section.heading_path,
                    heading_title=section.title,
                    heading_level=section.level,
                )
            )
    return chunks


def match_chunk_to_structure(
    chunk: StructuredChunk,
    structure_items: list[dict[str, Any]],
) -> tuple[str | None, str | None, list[str]]:
    """Map a heading path to confirmed structure before using an LLM classifier."""

    headings = [_normalize_title(title) for title in chunk.heading_path]
    best_item: dict[str, Any] | None = None
    best_score = 0

    for item in structure_items:
        score = 0
        chapter_title = _normalize_title(str(item.get("chapter_title") or ""))
        section_title = _normalize_title(str(item.get("section_title") or ""))
        point_name = _normalize_title(str(item.get("knowledge_point_name") or ""))

        for heading in headings:
            if section_title and _titles_match(heading, section_title):
                score += 10
            if chapter_title and _titles_match(heading, chapter_title):
                score += 5
            if point_name and _titles_match(heading, point_name):
                score += 3

        if score > best_score:
            best_item = item
            best_score = score

    if not best_item or best_score < 5:
        return None, None, []

    keywords = [
        str(value)
        for value in (
            best_item.get("chapter_title"),
            best_item.get("section_title"),
            best_item.get("knowledge_point_name"),
        )
        if value
    ]
    return (
        best_item.get("section_id") or best_item.get("chapter_id"),
        best_item.get("knowledge_point_id"),
        keywords,
    )


def _leading_toc_heading_indexes(lines: list[str]) -> set[int]:
    entries, first_body_heading_index = _leading_toc_entries(lines)
    if first_body_heading_index is None:
        return set()
    return {index for index, _, _ in entries}


def _leading_toc_entries(
    lines: list[str],
) -> tuple[list[tuple[int, str, str]], int | None]:
    candidates: list[tuple[int, str, str]] = []
    first_heading: str | None = None
    for index, line in enumerate(lines[:120]):
        match = _NUMBERED_HEADING_RE.match(line.strip())
        if not match:
            continue
        number = match.group("number")
        title = match.group("title").strip()
        normalized_heading = _normalize_title(f"{number} {title}")
        if first_heading is None:
            first_heading = normalized_heading
        elif normalized_heading == first_heading and len(candidates) >= 3:
            return candidates, index
        candidates.append((index, number, title))
    return [], None


def _split_section_content(content: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_length = 0
            chunks.extend(_split_long_text(paragraph, chunk_size, overlap))
            continue

        added_length = len(paragraph) + (2 if current else 0)
        if current and current_length + added_length > chunk_size:
            chunks.append("\n\n".join(current))
            overlap_text = _tail_text(chunks[-1], overlap)
            current = [overlap_text, paragraph] if overlap_text else [paragraph]
            current_length = sum(len(item) for item in current) + 2 * (len(current) - 1)
        else:
            current.append(paragraph)
            current_length += added_length

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def _tail_text(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    return text[-overlap:].strip()


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _normalize_title(value: str) -> str:
    value = re.sub(r"^#{1,6}\s+", "", value.strip())
    value = re.sub(r"^\d+(?:\.\d+)*\s*", "", value)
    return re.sub(r"[\s:：，,。.!！?？\-—_]+", "", value).lower()


def _clean_numbered_heading(number: str, title: str) -> str:
    title = re.sub(r"\s+[a-zA-Z]$", "", title.strip())
    return f"{number} {title}".strip()


def _titles_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left == right or (min(len(left), len(right)) >= 4 and (left in right or right in left))


def _is_probable_heading(title: str) -> bool:
    stripped = title.strip()
    if not stripped or len(stripped) > 160:
        return False
    if any(token in stripped for token in ("=", "plt.", "print(", "import ", "return ")):
        return False
    if stripped.startswith((",", ".", ";", ":", "，", "。")):
        return False
    return True
