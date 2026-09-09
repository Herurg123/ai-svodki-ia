from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_pulse as sp
import source_pulse_supplement_v12 as v12
import source_pulse_supplement_v13 as v13

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "source-pulse-global-official-2026-09-09.json"
REGISTRY = ROOT / "automation" / "config" / "source-pulse-v1.json"
NEW_SOURCE_IDS = {"openai_news_rss", "qualcomm_news_ai", "nsa_ai_news"}


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def registry_contract() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def source_map() -> dict[str, sp.SourceDefinition]:
    return {source.id: source for source in sp.load_registry(REGISTRY)}


class GlobalOfficialRegistryTests(unittest.TestCase):
    def test_only_bounded_tier_a_official_routes_are_added(self):
        payload = registry_contract()
        rows = {str(row["id"]): row for row in payload["sources"]}
        self.assertEqual(len(rows), 16)
        self.assertTrue(NEW_SOURCE_IDS.issubset(rows))
        for source_id in NEW_SOURCE_IDS:
            row = rows[source_id]
            self.assertEqual(row["tier"], "A")
            self.assertEqual(row["role"], "official")
            self.assertEqual(row["region"], "global")
            self.assertLessEqual(int(row["max_items"]), 16)

    def test_registry_preserves_zero_paid_and_recovery_contract(self):
        payload = registry_contract()
        self.assertTrue(payload["supplemental_candidate_influence"])
        self.assertFalse(payload["repoll_on_recovery"])
        invariants = fixture()["invariants"]
        self.assertEqual(fixture()["paid_api_calls"], 0)
        self.assertEqual(fixture()["web_search_operations"], 0)
        self.assertEqual(fixture()["search_budget_delta"], 0)
        self.assertEqual(invariants["primary_searches_unchanged"], 12)
        self.assertEqual(invariants["agency_rescue_searches_max_unchanged"], 1)
        self.assertEqual(invariants["hybrid_searches_max_unchanged"], 5)
        self.assertEqual(invariants["coverage_searches_max_unchanged"], 7)
        self.assertEqual(invariants["whole_pipeline_ceiling_unchanged"], 25)


class GlobalOfficialParserTests(unittest.TestCase):
    def test_openai_rss_surfaces_sep6_and_sep8_controls(self):
        payload = fixture()["representative_payloads"]["openai_rss"]
        source = source_map()["openai_news_rss"]
        rows = sp.parse_body(source, payload, source.url)
        by_title = {row.title: row for row in rows if sp.allowed_item(row, source)}
        self.assertEqual(set(by_title), {
            "Research acceleration: The view inside OpenAI",
            "An Alien Mind",
            "Introducing ChatGPT Images 2.5",
        })
        self.assertEqual(
            by_title["Research acceleration: The view inside OpenAI"].published_date,
            date(2026, 9, 6),
        )
        self.assertEqual(
            by_title["Introducing ChatGPT Images 2.5"].published_date,
            date(2026, 9, 8),
        )

    def test_qualcomm_card_parser_keeps_ai_event_and_rejects_executive_noise(self):
        payload = fixture()["representative_payloads"]["qualcomm_html"]
        source = source_map()["qualcomm_news_ai"]
        rows = v13.parse_html_index_v13(payload, source.url)
        accepted = [row for row in rows if sp.allowed_item(row, source)]
        self.assertEqual(len(accepted), 1)
        self.assertIn("Amazon", accepted[0].title)
        self.assertEqual(accepted[0].published_date, date(2026, 9, 8))

    def test_nsa_ai_tag_parser_keeps_ai_control_and_rejects_unrelated_security(self):
        payload = fixture()["representative_payloads"]["nsa_html"]
        source = source_map()["nsa_ai_news"]
        rows = v13.parse_html_index_v13(payload, source.url)
        accepted = [row for row in rows if sp.allowed_item(row, source)]
        self.assertEqual(len(accepted), 1)
        self.assertIn("Distilling", accepted[0].title)
        self.assertEqual(accepted[0].published_date, date(2026, 9, 8))

    def test_stale_ai_item_stays_outside_exact_window(self):
        source = source_map()["qualcomm_news_ai"]
        item = sp.ParsedItem(
            title=(
                "The next frontier in AI inference infrastructure: Bringing compute near data "
                "with high bandwidth compute"
            ),
            url=(
                "https://www.qualcomm.com/news/onq/2026/07/"
                "the-next-frontier-in-ai-inference-infrastructure"
            ),
            published_date=date(2026, 7, 9),
            published_at=None,
            time_precision="date",
            source_item_id="stale",
        )
        self.assertTrue(sp.allowed_item(item, source))
        inside, _ = sp.within(
            item,
            datetime.fromisoformat("2026-09-06T04:01:03+03:00"),
            datetime.fromisoformat("2026-09-09T04:15:13+03:00"),
        )
        self.assertFalse(inside)


class GlobalOfficialHistoricalReplayTests(unittest.TestCase):
    def test_bounded_strict_recall_improves_without_claiming_unfixed_misses(self):
        controls = fixture()["historical_strict_controls"]
        self.assertEqual((controls["baseline_found"], controls["baseline_total"]), (6, 13))
        self.assertEqual((controls["proposed_found"], controls["baseline_total"]), (10, 13))
        self.assertGreater(controls["proposed_recall"], controls["baseline_recall"])
        self.assertAlmostEqual(
            controls["proposed_recall"] - controls["baseline_recall"], 4 / 13, places=9
        )
        self.assertEqual(set(controls["still_missed"]), {
            "tcs-hypervault-sep5",
            "reuters-openai-eu-incident-report-sep7",
            "firmus-openai-malaysia-sep8",
        })

    def test_real_supplement_path_promotes_five_first_party_rows_and_reuses_snapshot(self):
        data = fixture()
        by_url = {
            route["index_url"]: data["representative_payloads"][key]
            for route, key in zip(
                data["source_routes"],
                ("openai_rss", "qualcomm_html", "nsa_html"),
                strict=True,
            )
        }
        contract = registry_contract()
        subset = [row for row in contract["sources"] if row["id"] in NEW_SOURCE_IDS]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            research = root / "research.json"
            archive = root / "archive.json"
            registry = root / "registry.json"
            output = root / "diag"
            research.write_text(json.dumps({
                "status": "ok",
                "publication_date": "2026-09-09",
                "search_window": {
                    "start_at": "2026-09-06T04:01:03+03:00",
                    "end_at": "2026-09-09T04:15:13+03:00",
                    "latest_archive_at": "2026-09-07T04:01:03+03:00",
                },
                "coverage": [],
                "candidates": [],
                "regional_health": {
                    "russia": {"health_check_needed": True},
                    "china_asia": {"health_check_needed": True},
                },
            }, ensure_ascii=False) + "\n", encoding="utf-8")
            archive.write_text('{"items": []}\n', encoding="utf-8")
            registry.write_text(json.dumps({
                **{key: value for key, value in contract.items() if key != "sources"},
                "sources": subset,
            }, ensure_ascii=False) + "\n", encoding="utf-8")

            def fetcher(url: str, hosts: tuple[str, ...]) -> sp.FetchOutcome:
                del hosts
                body = by_url[url]
                return sp.FetchOutcome(url, url, "ok", 200, body, None, 1)

            def collector(**kwargs):
                return v12.run_source_pulse_v12(**kwargs, fetcher=fetcher)

            dates = {
                sp.norm_url(row["url"]): row["published_date"]
                for row in data["positive_cases"]
            }

            def page_fetcher(url: str):
                day = dates[sp.norm_url(url)]
                body = (
                    '<html><head><meta property="article:published_time" '
                    f'content="{day}T12:00:00+00:00">'
                    '<meta name="description" content="Artificial intelligence AI model research, '
                    'security, inference and data center infrastructure update."></head>'
                    '<body><p>Artificial intelligence model research and AI infrastructure details '
                    'are described in this official publication.</p></body></html>'
                )
                return body, url, 200

            first = v13.run_source_pulse_supplement(
                research_path=research,
                archive_path=archive,
                publication_date="2026-09-09",
                output_root=output,
                registry_path=registry,
                collector_fn=collector,
                page_fetcher=page_fetcher,
            )
            payload = json.loads(research.read_text(encoding="utf-8"))
            self.assertEqual(first["promotion"]["promoted_count"], 5)
            self.assertEqual(first["paid_api_calls"], 0)
            self.assertEqual(first["web_search_operations"], 0)
            self.assertEqual(len(payload["candidates"]), 5)
            self.assertTrue(payload["regional_health"]["russia"]["health_check_needed"])
            self.assertTrue(payload["regional_health"]["china_asia"]["health_check_needed"])

            def must_not_repoll(**kwargs):
                raise AssertionError("same-day recovery must reuse the saved Source Pulse snapshot")

            second = v13.run_source_pulse_supplement(
                research_path=research,
                archive_path=archive,
                publication_date="2026-09-09",
                output_root=output,
                registry_path=registry,
                collector_fn=must_not_repoll,
                page_fetcher=page_fetcher,
            )
            payload_after = json.loads(research.read_text(encoding="utf-8"))
            self.assertTrue(second["reused_snapshot"])
            self.assertEqual(len(payload_after["candidates"]), 5)
            self.assertEqual(second["paid_api_calls"], 0)
            self.assertEqual(second["web_search_operations"], 0)


if __name__ == "__main__":
    unittest.main()
