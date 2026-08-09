"""Index normalized law chunks into a persistent Chroma collection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings

from src.ingestion.chunker import LawChunk, load_chunks


@dataclass(frozen=True)
class IndexResult:
    status: str
    article_count: int
    chunk_count: int
    collection_count: int
    source_sha256: str
    embedding_model: str


def _new_store(
    *,
    persist_directory: str | Path,
    collection_name: str,
    embeddings: Embeddings,
    source_sha256: str,
    embedding_model: str,
) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_directory),
        collection_metadata={
            "source_sha256": source_sha256,
            "embedding_model": embedding_model,
            "schema_version": 1,
        },
        client_settings=Settings(anonymized_telemetry=False, is_persistent=True),
    )


def index_law_chunks(
    chunks: list[LawChunk],
    *,
    persist_directory: str | Path,
    collection_name: str,
    embedding_model: str,
    ollama_base_url: str,
    batch_size: int = 64,
    force: bool = False,
    embeddings: Embeddings | None = None,
) -> IndexResult:
    if not chunks:
        raise ValueError("색인할 청크가 없습니다.")
    if batch_size < 1:
        raise ValueError("batch_size는 1 이상이어야 합니다.")

    source_hashes = {str(chunk.metadata["source_sha256"]) for chunk in chunks}
    if len(source_hashes) != 1:
        raise ValueError("한 번의 색인에서는 동일한 원본 버전의 청크만 사용합니다.")
    source_sha256 = source_hashes.pop()
    expected_ids = {chunk.chunk_id for chunk in chunks}

    embeddings = embeddings or OllamaEmbeddings(
        model=embedding_model,
        base_url=ollama_base_url,
    )
    store = _new_store(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embeddings=embeddings,
        source_sha256=source_sha256,
        embedding_model=embedding_model,
    )
    existing = store.get(include=[])
    existing_ids = set(existing.get("ids", []))
    collection_metadata = store._collection.metadata or {}
    same_version = (
        collection_metadata.get("source_sha256") == source_sha256
        and collection_metadata.get("embedding_model") == embedding_model
    )

    if not force and same_version and existing_ids == expected_ids:
        return IndexResult(
            status="skipped",
            article_count=len({chunk.article_id for chunk in chunks}),
            chunk_count=len(chunks),
            collection_count=len(existing_ids),
            source_sha256=source_sha256,
            embedding_model=embedding_model,
        )

    if existing_ids:
        store._client.delete_collection(collection_name)
        store = _new_store(
            persist_directory=persist_directory,
            collection_name=collection_name,
            embeddings=embeddings,
            source_sha256=source_sha256,
            embedding_model=embedding_model,
        )

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        documents = [
            Document(page_content=chunk.content, metadata=chunk.metadata)
            for chunk in batch
        ]
        store.add_documents(documents=documents, ids=[chunk.chunk_id for chunk in batch])

    collection_count = store._collection.count()
    if collection_count != len(chunks):
        raise RuntimeError(
            f"색인 검증 실패: 예상 {len(chunks)}개, 실제 {collection_count}개"
        )

    return IndexResult(
        status="indexed",
        article_count=len({chunk.article_id for chunk in chunks}),
        chunk_count=len(chunks),
        collection_count=collection_count,
        source_sha256=source_sha256,
        embedding_model=embedding_model,
    )


def index_normalized_file(
    source_path: str | Path,
    **kwargs: object,
) -> IndexResult:
    max_chars = int(kwargs.pop("max_chars", 1800))
    return index_law_chunks(load_chunks(source_path, max_chars=max_chars), **kwargs)  # type: ignore[arg-type]
