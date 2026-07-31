from pathlib import Path
import unittest

from src.ingestion.docx_parser import parse_statute_docx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "tax.docx"


class TaxDocxParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata, cls.articles = parse_statute_docx(SOURCE)
        cls.by_number = {
            article.article_number: article for article in cls.articles
        }

    def test_document_version_is_preserved(self) -> None:
        self.assertEqual(self.metadata.law_name, "소득세법")
        self.assertEqual(self.metadata.effective_date, "2026. 1. 2.")
        self.assertEqual(self.metadata.law_number, "제21065호")
        self.assertEqual(len(self.metadata.source_sha256), 64)

    def test_article_1_structure(self) -> None:
        article = self.by_number["1조"]
        self.assertEqual(article.article_title, "목적")
        self.assertEqual(article.chapter, "제1장")
        self.assertEqual(article.chapter_title, "총칙")
        self.assertIn("조세부담의 형평", article.text)

    def test_article_4_contains_income_categories(self) -> None:
        article = self.by_number["4조"]
        self.assertEqual(article.article_title, "소득의 구분")
        self.assertIn("이자소득", article.text)
        self.assertIn("양도소득", article.text)

    def test_article_143_is_not_confused_with_sub_articles(self) -> None:
        article = self.by_number["143조"]
        self.assertEqual(
            article.article_title,
            "근로소득에 대한 원천징수영수증의 발급",
        )
        self.assertIn("다음 연도 2월 말일까지", article.text)
        self.assertIn("143조의2", self.by_number)

    def test_addendum_articles_are_not_indexed_as_main_articles(self) -> None:
        article_ids = [article.article_id for article in self.articles]
        self.assertEqual(len(article_ids), len(set(article_ids)))
        self.assertNotIn("이 법은 2026년 1월 1일부터 시행한다", self.by_number["1조"].text)

    def test_future_duplicate_article_versions_are_not_mixed_in(self) -> None:
        article = self.by_number["64조의3"]
        self.assertNotIn("가상자산소득금액", article.text)
        self.assertNotIn("[시행일: 2027. 1. 1.]", article.text)

    def test_whole_future_article_is_not_indexed(self) -> None:
        self.assertNotIn("164조의4", self.by_number)
        self.assertTrue(
            all("[시행일:" not in article.text for article in self.articles)
        )


if __name__ == "__main__":
    unittest.main()
