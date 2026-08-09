"""Create deterministic, structure-aware chunks from normalized law articles."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


STRUCTURE_RE = re.compile(r"^[①-⑳]|^\d+(?:의\d+)?\.|^[가-하]\.\s*")
REVISION_RE = re.compile(r"^\[(?:본조신설|전문개정|제목개정|종전 |시행일:)")


@dataclass(frozen=True)
class LawChunk:
    chunk_id: str
    document_id: str
    article_id: str
    article_number: str
    article_title: str
    chunk_index: int
    content: str
    metadata: dict[str, str | int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ChunkingError(ValueError):
    """Raised when normalized article data is invalid."""


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Split a long paragraph near whitespace without losing characters."""

    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        boundary = remaining.rfind(" ", 0, max_chars + 1)
        if boundary < max_chars // 2:
            boundary = max_chars
        pieces.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _article_parts(text: str, max_chars: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    units: list[str] = []
    for line in lines:
        if len(line) > max_chars:
            units.extend(_split_long_text(line, max_chars))
        elif REVISION_RE.match(line) and units:
            units[-1] = f"{units[-1]}\n{line}"
        elif STRUCTURE_RE.match(line) or not units:
            units.append(line)
        else:
            units.append(line)

    parts: list[str] = []
    current: list[str] = []
    current_length = 0
    for unit in units:
        added_length = len(unit) + (1 if current else 0)
        if current and current_length + added_length > max_chars:
            parts.append("\n".join(current))
            current = []
            current_length = 0
        current.append(unit)
        current_length += len(unit) + (1 if current_length else 0)
    if current:
        parts.append("\n".join(current))
    return parts


def build_chunks(
    payload: dict[str, object],
    *,
    max_chars: int = 1800,
) -> list[LawChunk]:
    """Build searchable chunks while preserving law/article context."""

    if max_chars < 300:
        raise ChunkingError("max_chars는 300 이상이어야 합니다.")

    document = payload.get("document")
    articles = payload.get("articles")
    if not isinstance(document, dict) or not isinstance(articles, list):
        raise ChunkingError("정규화 JSON에 document와 articles가 필요합니다.")

    required_document_fields = ("law_name", "law_number", "effective_date", "source_file", "source_sha256")
    if any(not document.get(field) for field in required_document_fields):
        raise ChunkingError("문서 메타데이터가 누락됐습니다.")

    document_id = f"{document['law_number']}:{document['source_sha256']}"
    chunks: list[LawChunk] = []

    for article in articles:
        if not isinstance(article, dict):
            raise ChunkingError("조문 데이터는 객체여야 합니다.")
        text = str(article.get("text", "")).strip()
        article_id = str(article.get("article_id", "")).strip()
        article_number = str(article.get("article_number", "")).strip()
        if not text or not article_id or not article_number:
            raise ChunkingError("조문 ID, 번호, 본문이 누락됐습니다.")

        title = str(article.get("article_title", ""))
        heading = f"{document['law_name']} 제{article_number}"
        if title:
            heading += f"({title})"

        for chunk_index, part in enumerate(_article_parts(text, max_chars)):
            content = part if chunk_index == 0 else f"{heading}\n{part}"
            chunk_id = f"{article_id}:chunk-{chunk_index:03d}"
            metadata: dict[str, str | int] = {
                "document_id": document_id,
                "article_id": article_id,
                "article_number": article_number,
                "article_title": title,
                "chapter": str(article.get("chapter", "")),
                "chapter_title": str(article.get("chapter_title", "")),
                "section": str(article.get("section", "")),
                "section_title": str(article.get("section_title", "")),
                "law_name": str(document["law_name"]),
                "law_number": str(document["law_number"]),
                "effective_date": str(document["effective_date"]),
                "source_file": str(document["source_file"]),
                "source_sha256": str(document["source_sha256"]),
                "chunk_index": chunk_index,
            }
            chunks.append(
                LawChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    article_id=article_id,
                    article_number=article_number,
                    article_title=title,
                    chunk_index=chunk_index,
                    content=content,
                    metadata=metadata,
                )
            )

    if not chunks:
        raise ChunkingError("생성된 청크가 없습니다.")
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ChunkingError("청크 ID가 중복됩니다.")
    return chunks


def load_chunks(source_path: str | Path, *, max_chars: int = 1800) -> list[LawChunk]:
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"정규화 JSON을 찾을 수 없습니다: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ChunkingError("정규화 JSON의 최상위는 객체여야 합니다.")
    return build_chunks(payload, max_chars=max_chars)
