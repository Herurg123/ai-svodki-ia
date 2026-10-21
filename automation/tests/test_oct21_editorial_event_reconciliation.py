"""Red-first Oct21 editorial reconciliation and semantic/section invariants."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from editorial_policy import read_policy, validate_article_policy
from editorial_reconciliation import (
    detect_event_repetitions,
    reconcile_exact_approved_incident,
    save_editorial_attempt,
)

POLICY = read_policy(ROOT / "automation" / "config" / "editorial.json")
MINIMAX = "https://www.minimax.io/blog/minimax-m31f"


def candidate(cid: str, title: str, url: str, org: str = "MiniMax", event: str = "release"):
    return {
        "id": cid,
        "title": title,
        "organization": org,
        "event_type": event,
        "event_summary": title,
        "geography": "world",
        "primary_source": {"url": url},
        "supporting_sources": [],
    }


class EditorialOct21RegressionTests(unittest.TestCase):
    def test_semantic_event_identity_detects_paraphrase_without_html_equality(self):
        title = "MiniMax выпустила модель M3.1 Flash"
        article = (
            "<h2>Мировые лидеры ИИ</h2>"
            "<h3>" + title + "</h3><p>Длинный рассказ про API и цены.</p>"
            '<p><a href="' + MINIMAX + '">источник</a></p>'
            "<h2>Китайские лидеры ИИ</h2>"
            "<h3>Новая модель MiniMax M3.1 Flash для агентов</h3>"
            "<p>Другой пересказ про программирование и контекст.</p>"
            '<p><a href="' + MINIMAX + '">анонс</a></p>'
        )
        cases = detect_event_repetitions(article, [candidate("cand-002", title, MINIMAX)])
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["candidate_id"], "cand-002")
        self.assertEqual(cases[0]["positions"], [1, 2])
        self.assertEqual(cases[0]["classification"], "same_candidate_event")

    def test_one_url_different_event_does_not_auto_delete(self):
        url = "https://example.org/releases"
        selected = [
            candidate("a", "Acme выпустила модель X", url, "Acme", "release"),
            candidate("b", "Acme закрыла сервис Y", url, "Acme", "shutdown"),
        ]
        article = (
            "<h2>Мировые лидеры ИИ</h2>"
            '<h3>Acme выпустила модель X</h3><p><a href="' + url + '">источник</a></p>'
            '<h3>Acme закрыла сервис Y</h3><p><a href="' + url + '">источник</a></p>'
        )
        issues = detect_event_repetitions(article, selected)
        self.assertFalse(any(item.get("classification") == "confirmed_duplicate" for item in issues))
        self.assertFalse(any(item.get("auto_removed") for item in issues))

    def test_without_exact_manifest_paraphrase_is_never_deleted(self):
        article = "<h2>Мировые лидеры ИИ</h2><h3>Foo</h3><p>A</p>"
        obj = {"selected_candidate_ids": ["a"], "digest": {"article_html": article}}
        original = copy.deepcopy(obj)
        with tempfile.TemporaryDirectory() as tmp:
            out, report = reconcile_exact_approved_incident(
                obj, [candidate("a", "Foo", "https://foo.org")],
                publication_date="2026-10-22",
                raw_path=Path(tmp) / "raw.json",
            )
        self.assertEqual(out, original)
        self.assertEqual(report["status"], "not_applicable")

    def test_editorial_attempts_are_immutable_across_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = save_editorial_attempt(
                root, "2026-10-21", "resp-one", '{"sample": 1}', "gpt-5.6-terra"
            )
            second = save_editorial_attempt(
                root, "2026-10-21", "resp-one", '{"sample": 1}', "gpt-5.6-terra"
            )
            self.assertEqual(first, second)
            self.assertEqual(first.read_text(), '{"sample": 1}')
            with self.assertRaises(ValueError):
                save_editorial_attempt(
                    root, "2026-10-21", "resp-one", '{"sample": 2}', "gpt-5.6-terra"
                )
            third = save_editorial_attempt(
                root, "2026-10-21", "resp-two", '{"sample": 2}', "gpt-5.6-terra"
            )
            self.assertNotEqual(first, third)
            self.assertTrue(first.exists())

    def test_chinese_story_under_world_heading_is_rejected_even_if_china_h2_exists(self):
        selected = [candidate("cand-002", "MiniMax выпустила новую модель", MINIMAX)]
        html = (
            "<p>Первое предложение. Второе предложение.</p>"
            "<h2>Мировые лидеры ИИ</h2>"
            "<h3>MiniMax выпустила новую модель</h3>"
            '<p>Первый абзац. <a href="' + MINIMAX + '">Источник</a>.</p>'
            "<p>Второй абзац.</p>"
            "<h2>Китайские лидеры ИИ</h2>"
            "<h2>Что это значит</h2><ol><li>Вывод 1</li><li>Вывод 2</li><li>Вывод 3</li><li>Вывод 4</li></ol>"
            '<h2>Все ИИ-Сводки</h2><p><a href="https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1">Архив ИИ-Сводок</a></p>'
        )
        errors, _, _ = validate_article_policy(html, selected, True, POLICY)
        self.assertTrue(
            any("фактическ" in err.lower() and ("китай" in err.lower() or "раздел" in err.lower()) for err in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
