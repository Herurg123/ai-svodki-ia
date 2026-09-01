from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_pulse as sp
import source_pulse_supplement_v12 as v12
import source_pulse_supplement_v13 as v13


class SourcePulseV13RecursionRegressionTests(unittest.TestCase):
    def _registry(self) -> list[sp.SourceDefinition]:
        return [
            sp.SourceDefinition(
                id="yandex_ir",
                tier="A",
                region="russia",
                role="official",
                adapter="html_index",
                url="https://ir.yandex.ru/press-releases?year=2026",
                allowed_hosts=("ir.yandex.ru",),
                include_url_regex=r"press-releases",
            )
        ]

    def _window(self) -> tuple[datetime, datetime]:
        return (
            datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        )

    def test_exact_v13_wrapper_path_keeps_v12_baseline_without_recursion(self):
        start_at, end_at = self._window()
        body = """
        <html><body>
          <a href="https://ir.yandex.ru/press-releases?year=2026&id=28-08-2026-01">
            Яндекс запускает новый ИИ-сервис
          </a>
          <span>28 августа 2026</span>
        </body></html>
        """

        def fetcher(url: str, hosts: tuple[str, ...]) -> sp.FetchOutcome:
            return sp.FetchOutcome(url, url, "ok", 200, body, None, 1)

        original = v12.parse_html_index_v12
        snapshot = v13.run_source_pulse_v13(
            registry=self._registry(),
            start_at=start_at,
            end_at=end_at,
            archive={"items": []},
            fetcher=fetcher,
            fetched_at=end_at,
        )

        self.assertIs(v12.parse_html_index_v12, original)
        self.assertEqual(snapshot["collector_version"], 13)
        self.assertEqual(snapshot["paid_api_calls"], 0)
        self.assertEqual(snapshot["web_search_operations"], 0)
        self.assertEqual(snapshot["summary"]["sources_parse_error"], 0)
        self.assertEqual(snapshot["summary"]["sources_unavailable"], 0)
        self.assertEqual(snapshot["summary"]["lead_count"], 1)
        self.assertEqual(snapshot["leads"][0]["published_date"], "2026-08-28")

    def test_v12_parser_is_restored_when_collector_raises(self):
        original_parser = v12.parse_html_index_v12
        original_collector = v12.run_source_pulse_v12

        def boom(**kwargs):
            raise RuntimeError("controlled collector failure")

        v12.run_source_pulse_v12 = boom
        try:
            with self.assertRaisesRegex(RuntimeError, "controlled collector failure"):
                v13.run_source_pulse_v13()
        finally:
            v12.run_source_pulse_v12 = original_collector

        self.assertIs(v12.parse_html_index_v12, original_parser)

    def test_source_unavailable_remains_complete_with_gap_not_parse_error(self):
        start_at, end_at = self._window()

        def unavailable(url: str, hosts: tuple[str, ...]) -> sp.FetchOutcome:
            return sp.FetchOutcome(url, None, "error", 503, None, "fixture unavailable", 1)

        snapshot = v13.run_source_pulse_v13(
            registry=self._registry(),
            start_at=start_at,
            end_at=end_at,
            archive={"items": []},
            fetcher=unavailable,
            fetched_at=end_at,
        )

        self.assertEqual(snapshot["summary"]["sources_unavailable"], 1)
        self.assertEqual(snapshot["summary"]["sources_parse_error"], 0)
        self.assertEqual(snapshot["summary"]["source_health_status"], "complete_with_gaps")
        self.assertEqual(snapshot["paid_api_calls"], 0)
        self.assertEqual(snapshot["web_search_operations"], 0)


if __name__ == "__main__":
    unittest.main()
