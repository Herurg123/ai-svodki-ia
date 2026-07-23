from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from editorial_policy import (  # noqa: E402
    normalize_article_html,
    order_candidates_by_article_links,
    read_policy,
    validate_article_policy,
)

POLICY = read_policy(ROOT / "automation" / "config" / "editorial.json")
DZEN = POLICY["dzen"]["html"]
FOOTNOTE = POLICY["meta_marking"]["footnote_html"]


def candidate(identifier: str, status: str = "none", geography: str = "world") -> dict:
    return {
        "id": identifier,
        "archive_status": status,
        "geography": geography,
        "organization": identifier,
        "primary_source": {"publisher": identifier, "url": f"https://example.com/{identifier}"},
    }


def base_article(headlines: list[str], paragraphs: int = 2) -> str:
    blocks = ["<p>Вступление из двух предложений. Второе предложение завершает вступление.</p>", "<h2>Мировые лидеры ИИ</h2>"]
    for headline in headlines:
        blocks.append(f"<h3>{headline}</h3>")
        for number in range(paragraphs):
            blocks.append(f"<p>Содержательный абзац {number + 1} для сюжета.</p>")
    blocks.extend([
        "<h2>Что это значит</h2>",
        "<ol><li>Первый вывод.</li><li>Второй вывод.</li><li>Третий вывод.</li><li>Четвёртый вывод.</li></ol>",
    ])
    return "\n".join(blocks)


class EditorialPolicyTests(unittest.TestCase):
    def test_short_digest_notice_and_dzen_are_normalized(self) -> None:
        candidates = [candidate("one"), candidate("two")]
        html, short_digest, _changes = normalize_article_html(
            base_article(["Первый сюжет", "Второй сюжет"]),
            candidates,
            POLICY,
        )
        self.assertTrue(short_digest)
        self.assertTrue(html.startswith("<p>День на новости выдался слабым - поэтому коротко</p>"))
        self.assertEqual(html.count(DZEN), 1)
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertEqual(errors, [])

    def test_normal_digest_has_no_short_notice(self) -> None:
        candidates = [candidate(str(index)) for index in range(6)]
        html, short_digest, _changes = normalize_article_html(
            base_article([f"Сюжет {index}" for index in range(6)]),
            candidates,
            POLICY,
        )
        self.assertFalse(short_digest)
        self.assertNotIn(POLICY["story_counts"]["short_digest_notice"], html.splitlines()[0])
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertEqual(errors, [])

    def test_meta_first_mention_and_footnote(self) -> None:
        candidates = [candidate("meta"), candidate("other")]
        source = base_article(["Meta представила функцию", "Рынок ответил Meta"])
        html, short_digest, _changes = normalize_article_html(source, candidates, POLICY)
        visible_without_footnote = html.replace(FOOTNOTE, "")
        self.assertIn("Meta* представила", visible_without_footnote)
        self.assertIn("ответил Meta", visible_without_footnote)
        self.assertEqual(html.count(FOOTNOTE), 1)
        self.assertGreater(html.rfind(FOOTNOTE), html.rfind(DZEN))
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertEqual(errors, [])

    def test_update_prefix_is_deterministic(self) -> None:
        candidates = [candidate("one", "update"), candidate("two", "none")]
        html, short_digest, _changes = normalize_article_html(
            base_article(["Старый заголовок", "Обновление: Новый сюжет"]),
            candidates,
            POLICY,
        )
        self.assertIn("<h3>Обновление: Старый заголовок</h3>", html)
        self.assertIn("<h3>Новый сюжет</h3>", html)
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertEqual(errors, [])

    def test_paragraph_count_is_enforced(self) -> None:
        candidates = [candidate("one")]
        html, short_digest, _changes = normalize_article_html(
            base_article(["Один сюжет"], paragraphs=1),
            candidates,
            POLICY,
        )
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertTrue(any("содержит 1 абзацев" in item for item in errors))

    def test_candidate_order_is_resolved_from_story_links(self) -> None:
        first = candidate("first")
        second = candidate("second")
        source = (
            "<p>Первое предложение вступления. Второе предложение вступления.</p>"
            "<h2>Мировые лидеры ИИ</h2>"
            "<h3>Сначала второй</h3>"
            "<p>Первый абзац.</p>"
            "<p>Второй абзац. <a href=\"https://example.com/second\">Источник</a>.</p>"
            "<h3>Затем первый</h3>"
            "<p>Первый абзац.</p>"
            "<p>Второй абзац. <a href=\"https://example.com/first\">Источник</a>.</p>"
            "<h2>Что это значит</h2>"
            "<ol><li>1.</li><li>2.</li><li>3.</li><li>4.</li></ol>"
        )
        ordered, errors = order_candidates_by_article_links(
            source, [first, second]
        )
        self.assertEqual(errors, [])
        self.assertEqual([item["id"] for item in ordered], ["second", "first"])

    def test_dzen_block_is_exact_and_unique(self) -> None:
        candidates = [candidate("one")]
        source = base_article(["Один сюжет"]) + "\n" + DZEN + "\n" + DZEN
        html, short_digest, _changes = normalize_article_html(source, candidates, POLICY)
        self.assertEqual(html.count(DZEN), 1)
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
