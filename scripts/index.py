#!/usr/bin/env python3
"""Create or refresh the local Chroma index from normalized law JSON."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.chroma_index import index_normalized_file  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정규화된 법령 JSON을 Chroma에 색인합니다.")
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "tax_articles.json",
    )
    parser.add_argument(
        "--persist-directory",
        type=Path,
        default=Path(os.getenv("CHROMA_PERSIST_DIR", PROJECT_ROOT / "chroma_db")),
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("CHROMA_COLLECTION", "tax-index"),
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("OLLAMA_EMBEDDING_MODEL", "snowflake-arctic-embed2"),
    )
    parser.add_argument(
        "--ollama-base-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    parser.add_argument("--max-chars", type=int, default=1800)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = index_normalized_file(
        args.source,
        persist_directory=args.persist_directory,
        collection_name=args.collection,
        embedding_model=args.embedding_model,
        ollama_base_url=args.ollama_base_url,
        max_chars=args.max_chars,
        batch_size=args.batch_size,
        force=args.force,
    )
    print(f"상태: {result.status}")
    print(f"조문: {result.article_count}개")
    print(f"청크: {result.chunk_count}개")
    print(f"Chroma 저장: {result.collection_count}개")
    print(f"임베딩 모델: {result.embedding_model}")
    print(f"원본 SHA-256: {result.source_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
