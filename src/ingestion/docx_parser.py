"""Parse a Korean statute DOCX into article-level records.

The parser intentionally uses only the Python standard library. A DOCX file is
an OOXML ZIP archive, so the source paragraphs can be read without requiring
Microsoft Word or a conversion tool.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NS}}}"

LAW_NAME_RE = re.compile(r"^\s*소득세법\s*$")
EFFECTIVE_DATE_RE = re.compile(r"\[시행\s+(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)\]")
PROMULGATION_RE = re.compile(
    r"\[법률\s+(제\d+호),\s*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.),\s*([^\]]+)\]"
)
ARTICLE_RE = re.compile(
    r"^제(?P<number>\d+조(?:의\d+)?)"
    r"(?:(?:\((?P<title>[^)]+)\))|(?=\s|$))"
    r"\s*(?P<body>.*)$"
)
CHAPTER_RE = re.compile(r"^(?P<label>제\d+장)\s+(?P<title>.+?)(?:\s*<.*)?$")
SECTION_RE = re.compile(r"^(?P<label>제\d+절)\s+(?P<title>.+?)(?:\s*<.*)?$")
ARTICLE_EFFECTIVE_RE = re.compile(
    r"^\[시행일:\s*(?P<date>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)\]\s*"
    r"제(?P<number>\d+조(?:의\d+)?)$"
)


@dataclass(frozen=True)
class LawMetadata:
    law_name: str
    effective_date: str
    law_number: str
    promulgation_date: str
    amendment_type: str
    source_file: str
    source_sha256: str


@dataclass(frozen=True)
class Article:
    article_id: str
    article_number: str
    article_title: str
    chapter: str
    chapter_title: str
    section: str
    section_title: str
    text: str
    source_file: str
    source_sha256: str
    law_name: str
    effective_date: str
    law_number: str
    promulgation_date: str
    amendment_type: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class DocxParseError(ValueError):
    """Raised when the DOCX does not contain the expected statute structure."""


def _normalize_text(value: str) -> str:
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def _read_paragraphs(source: Path) -> list[str]:
    try:
        with ZipFile(source) as archive:
            xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise DocxParseError(f"유효한 DOCX 문서가 아닙니다: {source}") from exc

    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []

    for paragraph in root.iter(f"{W}p"):
        fragments: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{W}t":
                fragments.append(node.text or "")
            elif node.tag == f"{W}tab":
                fragments.append("\t")
            elif node.tag in {f"{W}br", f"{W}cr"}:
                fragments.append("\n")

        text = _normalize_text("".join(fragments))
        if text:
            paragraphs.append(text)

    return paragraphs


def _file_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_korean_date(value: str) -> date:
    year, month, day = (int(part.strip()) for part in value.rstrip(".").split("."))
    return date(year, month, day)


def _extract_metadata(source: Path, paragraphs: list[str]) -> LawMetadata:
    header = "\n".join(paragraphs[:20])
    law_name = next(
        (text for text in paragraphs[:10] if LAW_NAME_RE.match(text)),
        "",
    )
    effective_match = EFFECTIVE_DATE_RE.search(header)
    promulgation_match = PROMULGATION_RE.search(header)

    missing: list[str] = []
    if not law_name:
        missing.append("법령명")
    if not effective_match:
        missing.append("시행일")
    if not promulgation_match:
        missing.append("법률 번호/공포일")
    if missing:
        raise DocxParseError(f"문서 헤더에서 {', '.join(missing)}을 찾지 못했습니다.")

    return LawMetadata(
        law_name=law_name,
        effective_date=_normalize_text(effective_match.group(1)),
        law_number=promulgation_match.group(1),
        promulgation_date=_normalize_text(promulgation_match.group(2)),
        amendment_type=_normalize_text(promulgation_match.group(3)),
        source_file=source.name,
        source_sha256=_file_sha256(source),
    )


def parse_statute_docx(source_path: str | Path) -> tuple[LawMetadata, list[Article]]:
    """Return document metadata and main-body articles from a statute DOCX.

    Consolidated-law DOCX files can contain an addendum whose article numbering
    starts again at Article 1. The initial pipeline indexes only the current
    main body and stops at the first standalone ``부칙`` heading.
    """

    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"DOCX 원본을 찾을 수 없습니다: {source}")

    paragraphs = _read_paragraphs(source)
    metadata = _extract_metadata(source, paragraphs)

    chapter = ""
    chapter_title = ""
    section = ""
    section_title = ""
    current: dict[str, str | list[str]] | None = None
    parsed: list[dict[str, str | list[str]]] = []
    seen_article_numbers: set[str] = set()
    skipping_future_version = False

    def finish_current() -> None:
        nonlocal current
        if current is not None:
            parsed.append(current)
            current = None

    for text in paragraphs:
        if text == "부칙" or text.startswith("부칙 <"):
            finish_current()
            break

        chapter_match = CHAPTER_RE.match(text)
        if chapter_match:
            finish_current()
            chapter = chapter_match.group("label")
            chapter_title = chapter_match.group("title")
            section = ""
            section_title = ""
            continue

        section_match = SECTION_RE.match(text)
        if section_match:
            finish_current()
            section = section_match.group("label")
            section_title = section_match.group("title")
            continue

        article_match = ARTICLE_RE.match(text)
        if article_match:
            finish_current()
            number = article_match.group("number")
            if number in seen_article_numbers:
                # 국가법령정보센터의 한글/Word 내려받기 문서는 현행 조문 뒤에
                # 장래 시행될 조문 전문을 같은 번호로 다시 싣기도 한다. 문서
                # 헤더의 시행일 현재 버전은 항상 첫 번째이므로 이후 전문은
                # 색인에서 제외한다.
                skipping_future_version = True
                continue

            skipping_future_version = False
            seen_article_numbers.add(number)
            title = article_match.group("title") or ""
            body = article_match.group("body")
            first_line = f"제{number}"
            if title:
                first_line += f"({title})"
            if body:
                first_line += f" {body}"

            current = {
                "article_number": number,
                "article_title": title,
                "chapter": chapter,
                "chapter_title": chapter_title,
                "section": section,
                "section_title": section_title,
                "lines": [first_line],
            }
            continue

        if current is not None and not skipping_future_version:
            lines = current["lines"]
            assert isinstance(lines, list)
            lines.append(text)

    finish_current()

    effective_date = _parse_korean_date(metadata.effective_date)
    current_records: list[dict[str, str | list[str]]] = []
    for record in parsed:
        lines = record["lines"]
        assert isinstance(lines, list)
        exclude_future_article = False
        searchable_lines: list[str] = []

        for line in lines:
            effective_match = ARTICLE_EFFECTIVE_RE.match(line)
            if (
                effective_match
                and effective_match.group("number") == record["article_number"]
                and _parse_korean_date(effective_match.group("date")) > effective_date
            ):
                exclude_future_article = True
            if not line.startswith("[시행일:"):
                searchable_lines.append(line)

        if not exclude_future_article:
            record["lines"] = searchable_lines
            current_records.append(record)

    articles = [
        Article(
            article_id=f"{metadata.law_number}:{record['article_number']}",
            article_number=str(record["article_number"]),
            article_title=str(record["article_title"]),
            chapter=str(record["chapter"]),
            chapter_title=str(record["chapter_title"]),
            section=str(record["section"]),
            section_title=str(record["section_title"]),
            text="\n".join(record["lines"]),  # type: ignore[arg-type]
            **asdict(metadata),
        )
        for record in current_records
    ]

    if not articles:
        raise DocxParseError("본문에서 조문을 찾지 못했습니다.")

    return metadata, articles
