from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from langchain_core.embeddings import DeterministicFakeEmbedding

from src.ingestion.chroma_index import index_law_chunks
from src.ingestion.chunker import LawChunk


def sample_chunks(source_hash: str = "hash-v1") -> list[LawChunk]:
    return [
        LawChunk(
            chunk_id="law:1:chunk-000",
            document_id=f"law:{source_hash}",
            article_id="law:1",
            article_number="1조",
            article_title="목적",
            chunk_index=0,
            content="제1조(목적) 테스트 법령의 목적이다.",
            metadata={
                "source_sha256": source_hash,
                "article_id": "law:1",
                "article_number": "1조",
            },
        ),
        LawChunk(
            chunk_id="law:2:chunk-000",
            document_id=f"law:{source_hash}",
            article_id="law:2",
            article_number="2조",
            article_title="정의",
            chunk_index=0,
            content="제2조(정의) 테스트 용어를 정의한다.",
            metadata={
                "source_sha256": source_hash,
                "article_id": "law:2",
                "article_number": "2조",
            },
        ),
    ]


class ChromaIndexTest(unittest.TestCase):
    def test_same_chunks_are_skipped_on_second_run(self) -> None:
        with TemporaryDirectory() as directory:
            kwargs = {
                "persist_directory": Path(directory),
                "collection_name": "test-index",
                "embedding_model": "fake-model",
                "ollama_base_url": "http://unused",
                "embeddings": DeterministicFakeEmbedding(size=16),
            }
            first = index_law_chunks(sample_chunks(), **kwargs)
            second = index_law_chunks(sample_chunks(), **kwargs)
            self.assertEqual(first.status, "indexed")
            self.assertEqual(second.status, "skipped")
            self.assertEqual(second.collection_count, 2)


if __name__ == "__main__":
    unittest.main()
