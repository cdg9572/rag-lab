#!/usr/bin/env python3
"""Convert the source statute DOCX into reviewable article-level JSON."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.docx_parser import parse_statute_docx  # noqa: E402


DEFAULT_SOURCE = PROJECT_ROOT / "tax.docx"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "tax_articles.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="소득세법 DOCX를 조문 단위 JSON으로 변환합니다."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata, articles = parse_statute_docx(args.source)
    payload = {
        "schema_version": 1,
        "document": asdict(metadata),
        "statistics": {
            "article_count": len(articles),
            "chapter_count": len({item.chapter for item in articles if item.chapter}),
            "section_count": len(
                {
                    (item.chapter, item.section)
                    for item in articles
                    if item.section
                }
            ),
        },
        "articles": [article.to_dict() for article in articles],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"원본: {args.source}")
    print(f"출력: {args.output}")
    print(f"법령: {metadata.law_name} ({metadata.law_number})")
    print(f"시행일: {metadata.effective_date}")
    print(f"조문: {len(articles)}개")
    print(f"장: {payload['statistics']['chapter_count']}개")
    print(f"절: {payload['statistics']['section_count']}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
