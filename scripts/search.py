#!/usr/bin/env python3
"""Inspect vector-search results without invoking the chat LLM."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chroma 벡터 검색 결과를 확인합니다.")
    parser.add_argument("구문", help="검색할 질문")
    parser.add_argument("--top-k", type=int, default=5)
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top_k < 1:
        raise ValueError("top-k는 1 이상이어야 합니다.")

    store = Chroma(
        collection_name=args.collection,
        persist_directory=str(args.persist_directory),
        embedding_function=OllamaEmbeddings(
            model=args.embedding_model,
            base_url=args.ollama_base_url,
        ),
        client_settings=Settings(anonymized_telemetry=False, is_persistent=True),
    )
    if store._collection.count() == 0:
        raise RuntimeError("Chroma 색인이 비어 있습니다. scripts/index.py를 먼저 실행하세요.")

    documents = store.similarity_search(args.구문, k=args.top_k)
    print(f"질문: {args.구문}")
    for rank, document in enumerate(documents, start=1):
        metadata = document.metadata
        print(
            f"{rank}. 제{metadata.get('article_number')} "
            f"{metadata.get('article_title', '')} "
            f"(청크 {metadata.get('chunk_index', 0)})"
        )
        print(f"   {document.page_content[:120].replace(chr(10), ' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
