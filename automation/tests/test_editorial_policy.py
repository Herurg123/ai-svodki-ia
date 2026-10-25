from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from editorial_policy import (  # noqa: E402
    normalize_article_html,
    normalize_candidate_ids,
    expected_editorial_heading,
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
    def test_candidate_ids_are_normalized_after_research(self) -> None:
        candidates = [
            {"id": "cand-001", "title": "Первый"},
            {"id": "cand-001", "title": "Второй"},
            {"id": "cand-009", "title": "Третий"},
        ]

        changes = normalize_candidate_ids(candidates)

        self.assertEqual(
            [item["id"] for item in candidates],
            ["cand-001", "cand-002", "cand-003"],
        )
        self.assertEqual(
            changes,
            [
                {"old_id": "cand-001", "new_id": "cand-002"},
                {"old_id": "cand-009", "new_id": "cand-003"},
            ],
        )

    def test_short_digest_notice_and_dzen_are_normalized(self) -> None:
        candidates = [candidate("one"), candidate("two")]
        html, short_digest, _changes = normalize_article_html(
            base_article(["Первый сюжет", "Второй сюжет"]),
            candidates,
            POLICY,
        )
        self.assertTrue(short_digest)
        self.assertTrue(html.startswith("<p><em>Новостей сегодня меньше, чем обычно</em></p>"))
        self.assertEqual(html.count(DZEN), 1)
        errors, _warnings, _analysis = validate_article_policy(
            html, candidates, short_digest, POLICY
        )
        self.assertEqual(errors, [])

    def test_normal_digest_has_no_short_notice(self) -> None:
        candidates = [candidate(str(index)) for index in range(7)]
        html, short_digest, _changes = normalize_article_html(
            base_article([f"Сюжет {index}" for index in range(7)]),
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


    def test_incidental_moonshot_tool_does_not_reclassify_cybercrime(self) -> None:
        incident = candidate("cyber")
        incident["organization"] = "CyberCartel; Anthropic; xAI; Moonshot AI; Straiker"
        incident["title"] = (
            "CyberCartel использовала Claude, Grok и Moonshot для атак в Латинской Америке"
        )
        self.assertEqual(
            expected_editorial_heading(incident, POLICY), "Мировые лидеры ИИ"
        )
        normalized, short, changes = normalize_article_html(
            base_article(["CyberCartel использовала Claude, Grok и Moonshot"]),
            [incident],
            POLICY,
        )
        self.assertFalse(
            any(item["field"] == "article_html.story_section" for item in changes)
        )
        errors, _, _ = validate_article_policy(normalized, [incident], short, POLICY)
        self.assertEqual(errors, [])

    def test_strong_chinese_actor_moves_story_and_preserves_exact_links(self) -> None:
        chinese = candidate("china")
        chinese["organization"] = "Moonshot AI; Reuters"
        chinese["title"] = "Moonshot AI выпустила Kimi"
        western = candidate("west")
        western["organization"] = "CyberCartel; Moonshot AI"
        western["title"] = "CyberCartel применила инструменты Moonshot AI"
        original = (
            "<p>Первое предложение вступления. Второе предложение.</p>"
            "<h2>Мировые лидеры ИИ</h2>"
            '<h3>Релиз Kimi</h3><p>Первый абзац.</p>'
            '<p>Второй <a href="https://example.com/china">источник Kimi</a>.</p>'
            '<h3>CyberCartel</h3><p>Первый абзац.</p>'
            '<p>Второй <a href="https://example.com/west">источник инцидента</a>.</p>'
            "<h2>Что это значит</h2>"
            "<ol><li>Раз</li><li>Два</li><li>Три</li><li>Четыре</li></ol>"
        )
        html, short, changes = normalize_article_html(
            original, [chinese, western], POLICY
        )
        self.assertEqual(
            [x["candidate_id"] for x in changes
             if x["field"] == "article_html.story_section"],
            ["china"],
        )
        self.assertLess(html.index("<h3>CyberCartel"), html.index("<h3>Релиз Kimi"))
        self.assertLess(
            html.index("<h2>Китайские лидеры ИИ</h2>"),
            html.index("<h3>Релиз Kimi"),
        )
        self.assertEqual(html.count("https://example.com/china"), 1)
        self.assertEqual(html.count("https://example.com/west"), 1)
        order, errors = order_candidates_by_article_links(html, [chinese, western])
        self.assertEqual(errors, [])
        self.assertEqual([item["id"] for item in order], ["west", "china"])
        policy_errors, _, _ = validate_article_policy(html, order, short, POLICY)
        self.assertEqual(policy_errors, [])

    def test_russian_story_is_relocated_without_publishing_duplicate(self) -> None:
        russian = candidate("ru", geography="russia")
        world = candidate("world")
        original = (
            "<p>Первое предложение вступления. Второе предложение.</p>"
            "<h2>Мировые лидеры ИИ</h2>"
            '<h3>Российское событие</h3><p>Первый абзац.</p>'
            '<p><a href="https://example.com/ru">Второй абзац</a>.</p>'
            '<h3>Мировое событие</h3><p>Первый абзац.</p>'
            '<p><a href="https://example.com/world">Второй абзац</a>.</p>'
            "<h2>Что это значит</h2>"
            "<ol><li>Раз</li><li>Два</li><li>Три</li><li>Четыре</li></ol>"
        )
        html, short, changes = normalize_article_html(
            original, [russian, world], POLICY
        )
        self.assertEqual(
            len([c for c in changes if c["field"] == "article_html.story_section"]), 1
        )
        self.assertLess(
            html.index("<h3>Мировое событие"),
            html.index("<h2>Российские лидеры ИИ</h2>"),
        )
        self.assertEqual(html.count("<h3>Российское событие"), 1)
        self.assertEqual(html.count("<h3>Мировое событие"), 1)
        order, errors = order_candidates_by_article_links(html, [russian, world])
        self.assertEqual(errors, [])
        policy_errors, _, _ = validate_article_policy(html, order, short, POLICY)
        self.assertEqual(policy_errors, [])

    def test_empty_optional_china_heading_is_removed_without_new_story(self) -> None:
        world = candidate("world")
        article = (
            base_article(["Мировой сюжет"]).replace(
                "<h2>Что это значит</h2>",
                "<h2>Китайские лидеры ИИ</h2><h2>Что это значит</h2>",
            )
        )
        html, short, changes = normalize_article_html(article, [world], POLICY)
        self.assertNotIn("<h2>Китайские лидеры ИИ</h2>", html)
        self.assertTrue(
            any(change["field"] == "article_html.empty_section" for change in changes)
        )
        self.assertEqual(
            validate_article_policy(html, [world], short, POLICY)[0], []
        )

    def test_section_repair_leaves_unbalanced_html_for_strict_validation(self) -> None:
        chinese = candidate("china")
        chinese["organization"] = "MiniMax"
        bad = (
            "<p>Начало. Продолжение.</p>"
            "<h2>Мировые лидеры ИИ</h2>"
            "<h3>MiniMax выпустила модель</h3><p>Незакрытый параграф"
        )
        html, _short, changes = normalize_article_html(bad, [chinese], POLICY)
        self.assertFalse(
            any(x["field"] == "article_html.story_section" for x in changes)
        )
        self.assertIn("Незакрытый параграф", html)

if __name__ == "__main__":
    unittest.main()
