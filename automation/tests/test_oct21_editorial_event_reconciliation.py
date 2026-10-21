"""Red-first Oct21 editorial reconciliation and semantic/section invariants."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from editorial_policy import read_policy, validate_article_policy
import editorial_reconciliation as recon
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

    def test_different_sources_same_event_metadata_is_flagged_without_removal(self):
        first = candidate("a", "Acme анонсировала новую платформу X", "https://a.org/one",
                          "Acme", "release")
        second = candidate("b", "Acme анонсировала новую платформу X", "https://b.org/two",
                           "Acme", "release")
        html = (
            "<h2>Мировые лидеры ИИ</h2>"
            '<h3>Acme анонсировала новую платформу X</h3><p><a href="https://a.org/one">A</a></p>'
            '<h3>Acme анонсировала новую платформу X</h3><p><a href="https://b.org/two">B</a></p>'
        )
        issues = detect_event_repetitions(html, [first, second])
        self.assertEqual(issues[0]["classification"], "possible_same_event")
        self.assertFalse(issues[0]["auto_removed"])

    def test_exact_incident_reconciliation_requires_protected_journal_identity(self):
        title = "MiniMax выпустила агентную модель M3.1 Flash"
        story = lambda body: (
            "<h3>" + title + "</h3><p>" + body
            + '</p><p><a href="' + MINIMAX + '">анонс</a></p>'
        )
        parts = ["<h2>Мировые лидеры ИИ</h2>"]
        parts.extend("<h3>Другой сюжет</h3><p>x</p><p>y</p>" for _ in range(1))
        detailed = story("Оригинальная подробная информация про релиз")
        parts.append(detailed)
        parts.extend("<h3>Другое событие</h3><p>x</p><p>y</p>" for _ in range(5))
        parts.append("<h2>Китайские лидеры ИИ</h2>")
        paraphrase = story("Отдельный более краткий пересказ")
        parts.append(paraphrase)
        parts.append("<h2>Что это значит</h2><ol><li>Итог</li></ol>")
        source = "".join(parts)
        selected = ["cand-001", "cand-002", "cand-003", "cand-004",
                    "cand-005", "cand-006", "cand-013"]
        original = {"selected_candidate_ids": selected,
                    "digest": {"article_html": source}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "editorial-output-raw.json"
            raw.write_text(json.dumps(original, ensure_ascii=False))
            journal = root / "journal.json"
            seal = {"state": "response_saved", **recon.JOURNAL_IDENTITY}
            journal.write_text(json.dumps(seal))
            with patch.object(recon, "RAW_SHA", recon.sha(raw.read_bytes())), \
                 patch.object(recon, "ARTICLE_SHA", recon.sha(source)), \
                 patch.object(recon, "DETAIL_SHA", recon.sha(detailed)), \
                 patch.object(recon, "PARAPHRASE_SHA", recon.sha(paraphrase)), \
                 patch.object(recon, "APPROVED_OUTPUT_SHA",
                              recon.sha(source.replace("<h3>" + title + "</h3><p>Оригинальная подробная информация про релиз</p><p><a href=\"" + MINIMAX + "\">анонс</a></p>", "", 1)
                                       .replace("Отдельный более краткий пересказ", "Оригинальная подробная информация про релиз"))):
                out, audit = reconcile_exact_approved_incident(
                    original, [candidate("cand-002", title, MINIMAX)],
                    publication_date="2026-10-21", raw_path=raw, journal_path=journal,
                )
                self.assertEqual(audit["status"], "applied")
                self.assertEqual(out["digest"]["article_html"].count(title), 1)
                self.assertIn("<h2>Китайские лидеры ИИ</h2>" + detailed,
                              out["digest"]["article_html"])
                self.assertEqual(out["selected_candidate_ids"], recon.AFTER)
                self.assertEqual(original["digest"]["article_html"], source)
                self.assertEqual(raw.read_text(), json.dumps(original, ensure_ascii=False))
                journal.write_text(json.dumps({"state": "response_saved",
                                               **recon.JOURNAL_IDENTITY,
                                               "archive_sha256": "tampered"}))
                with self.assertRaisesRegex(ValueError, "archive_sha256"):
                    reconcile_exact_approved_incident(
                        original, [candidate("cand-002", title, MINIMAX)],
                        publication_date="2026-10-21", raw_path=raw, journal_path=journal,
                    )

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

    def test_public_artifact_mapping_rejects_a_story_in_wrong_region(self):
        import validate_digest_artifact as artifact_validator

        selected = [candidate("cand-002", "MiniMax выпустила новую модель", MINIMAX)]
        html = (
            '<h2>Мировые лидеры ИИ</h2><h3>MiniMax выпустила новую модель</h3>'
            '<p><a href="' + MINIMAX + '">источник</a></p>'
            '<h2>Китайские лидеры ИИ</h2>'
        )
        report = {"errors": [], "warnings": []}
        artifact_validator.validate_story_mapping(
            html,
            {"candidates": selected},
            {"selected_candidate_ids": ["cand-002"]},
            {"stories": [{
                "candidate_id": "cand-002",
                "headline": "MiniMax выпустила новую модель",
                "sources": [{"url": MINIMAX}],
            }]},
            report,
        )
        codes = [item["code"] for item in report["errors"]]
        self.assertIn("story_section_mismatch", codes)

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
