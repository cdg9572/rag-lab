from dataclasses import asdict
from pathlib import Path
import unittest

from src.ingestion.chunker import ChunkingError, build_chunks
from src.ingestion.docx_parser import parse_statute_docx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCX_SOURCE = PROJECT_ROOT / "tax.docx"


class LawChunkerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        metadata, articles = parse_statute_docx(DOCX_SOURCE)
        cls.payload = {
            "document": asdict(metadata),
            "articles": [article.to_dict() for article in articles],
        }
        cls.chunks = build_chunks(cls.payload, max_chars=1800)

    def test_all_articles_produce_chunks_with_unique_ids(self) -> None:
        article_ids = {chunk.article_id for chunk in self.chunks}
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        self.assertEqual(len(article_ids), 325)
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        self.assertGreaterEqual(len(self.chunks), 325)

    def test_chunk_metadata_preserves_article_context(self) -> None:
        chunk = next(item for item in self.chunks if item.article_number == "143조")
        self.assertEqual(chunk.article_title, "근로소득에 대한 원천징수영수증의 발급")
        self.assertEqual(chunk.metadata["chapter"], "제5장")
        self.assertEqual(chunk.metadata["section"], "제1절")
        self.assertEqual(chunk.metadata["effective_date"], "2026. 1. 2.")
        self.assertIn("다음 연도 2월 말일까지", chunk.content)

    def test_long_article_is_split_and_each_part_keeps_heading(self) -> None:
        grouped = [item for item in self.chunks if item.article_number == "21조"]
        self.assertGreater(len(grouped), 1)
        for chunk in grouped[1:]:
            self.assertTrue(chunk.content.startswith("소득세법 제21조(기타소득)"))

    def test_same_input_produces_same_chunk_ids(self) -> None:
        second = build_chunks(self.payload, max_chars=1800)
        self.assertEqual(
            [chunk.chunk_id for chunk in self.chunks],
            [chunk.chunk_id for chunk in second],
        )

    def test_invalid_payload_is_rejected(self) -> None:
        with self.assertRaises(ChunkingError):
            build_chunks({"document": {}, "articles": []})


if __name__ == "__main__":
    unittest.main()
