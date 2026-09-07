"""Development regressions from exact Sep-5 evidence, without paid retrieval."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation/scripts"))
import ensure_story_coverage as coverage
import source_freshness as freshness
import recover_digest_artifact as recovery
from publication_evidence_adapters import first_party_evidence, OPENAI_NEWS_FEED
from source_resolution_evidence import collect_source_failure_signals

F = json.loads((ROOT / "automation/fixtures/recall/source-resolution-daybreak-2026-09-05.json").read_text())
WINDOW = F["primary"]["search_window"]


def signals(report=None, primary=None):
    return collect_source_failure_signals(
        report or F["source_freshness"], primary or F["primary"], search_window=WINDOW,
    )


class SourceFailureEvidenceTests(unittest.TestCase):
    def test_exact_legacy_daybreak_enters_prompt_without_reviving_candidate(self):
        before = copy.deepcopy(F)
        rows = signals()
        self.assertEqual(len(rows), 1)
        prompt = coverage.build_resolution_prompt(search_window=WINDOW, cluster=rows, archive={})
        for text in (F["daybreak"]["primary_source"]["url"], "403", "Daybreak", "2026-09-03"):
            self.assertIn(text, prompt)
        self.assertNotIn("recommendation", rows[0])
        self.assertEqual(F, before)

    def test_no_legacy_identity_borrowing_or_final_cap_loss(self):
        for mutation in ("title", "url", "cap", "ambiguous"):
            primary = copy.deepcopy(F["primary"])
            raw = primary["accepted_events"][0]
            if mutation == "title": raw["title"] = "Different OpenAI event"
            if mutation == "url": raw["primary_source"]["url"] += "/different"
            if mutation == "cap": primary["final_candidates"] = []
            if mutation == "ambiguous": primary["accepted_events"].append(copy.deepcopy(raw))
            with self.subTest(mutation=mutation): self.assertEqual(signals(primary=primary), [])

    def test_stale_low_signal_unconfirmed_and_other_windows_stay_out(self):
        for mutation in ("stale", "old_source", "low", "unconfirmed", "window"):
            primary, report = copy.deepcopy(F["primary"]), copy.deepcopy(F["source_freshness"])
            raw = primary["accepted_events"][0]
            record = report["runs"][0]["candidates"][0]
            if mutation == "stale": record["event_freshness_status"] = "stale"
            if mutation == "old_source": record["status"] = "excluded_outside_window"
            if mutation == "low": raw["significance_score"] = 2
            if mutation == "unconfirmed": raw["verification_status"] = "unconfirmed"
            if mutation == "window": report["runs"][0]["search_window"]["end_at"] = "2026-09-06T00:00:00Z"
            with self.subTest(mutation=mutation): self.assertEqual(signals(report, primary), [])

    def test_duplicate_runs_do_not_multiply_signals_and_later_success_retires(self):
        report = copy.deepcopy(F["source_freshness"])
        report["runs"].append(copy.deepcopy(report["runs"][0]))
        self.assertEqual(len(signals(report)), 1)
        report["runs"][-1]["candidates"][0]["status"] = "verified_fresh"
        self.assertEqual(signals(report), [])

    def test_fresh_failure_snapshot_preserves_original_before_gate(self):
        raw = copy.deepcopy(F["daybreak"])
        def blocked(_url): raise freshness.SourceFreshnessError("HTTP 403")
        record = freshness.verify_candidate(raw, start_at=datetime.fromisoformat(WINDOW["start_at"]),
            end_at=datetime.fromisoformat(WINDOW["end_at"]), fetcher=blocked)
        self.assertEqual(raw["recommendation"], "exclude")
        self.assertEqual(record["candidate_evidence"], F["daybreak"])
        report = {"runs": [{"search_window": WINDOW, "candidates": [record]}]}
        self.assertEqual(len(signals(report, {"accepted_events": [], "final_candidates": []})), 1)

    def test_six_pass_history_survives_error_and_recovery_makes_zero_calls(self):
        rows = signals()
        mandatory = [{"direction_id": d, "status": "checked", "attempt": 1,
                      "api": {"status": "completed", "web_search_calls_completed": 1}}
                     for d in coverage.AUDIT_DIRECTION_IDS]
        plan = {"publication_date": "2026-09-05", "audit_status": "complete",
                "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
                "attempts": copy.deepcopy(mandatory), "search_budget": {"maximum_calls": 7, "completed_calls": 6, "remaining_calls": 1}}
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "coverage-audit.json"
            def fail(**_kwargs):
                saved = json.loads(checkpoint.read_text())
                self.assertEqual(saved["attempts"][-1]["status"], "search_started")
                self.assertEqual(saved["search_budget"]["remaining_calls"], 0)
                raise TimeoutError("provider outcome unknown")
            with patch.object(coverage._runtime, "_report_path", return_value=checkpoint), patch.object(coverage._runtime, "_policy_audit_request", side_effect=fail) as transport:
                result = coverage._run_resolution(plan=plan, signals=rows, api_key="unused", model="unused",
                    search_window=WINDOW, archive={}, maximum_web_search_calls=7)
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(result["attempts"][:6], mandatory)
            self.assertEqual(result["attempts"][-1]["status"], "indeterminate_after_error")
            with patch.object(coverage, "_required_signals", return_value=rows), patch.object(coverage, "_V8_EXECUTE", side_effect=AssertionError("paid replay")):
                recovered = coverage.execute_audit_plan(api_key="unused", model="unused", template="", publication_date="2026-09-05",
                    search_window=WINDOW, missing_total=1, maximum_web_search_calls=7, existing_candidates=[], archive={}, prior_plan=json.loads(checkpoint.read_text()))
            self.assertEqual(recovered["attempts"], result["attempts"])
            self.assertEqual(recovered["search_budget"]["remaining_calls"], 0)
            with patch.object(coverage, "_required_signals", return_value=[]), patch.object(coverage, "_V8_EXECUTE", side_effect=AssertionError("paid replay after missing evidence")):
                recovered = coverage.execute_audit_plan(api_key="unused", model="unused", template="", publication_date="2026-09-05",
                    search_window=WINDOW, missing_total=1, maximum_web_search_calls=7, existing_candidates=[], archive={}, prior_plan=result)
            self.assertEqual(recovered["attempts"], result["attempts"])

    def test_unrelated_openai_event_cannot_resolve_or_join_daybreak(self):
        row = signals()[0]
        candidate = copy.deepcopy(F["daybreak"])
        candidate.update(title="OpenAI Astra model release", event_summary="OpenAI model release", keywords=["OpenAI", "Astra"])
        self.assertFalse(coverage._candidate_matches_cluster(candidate, [row]))
        other = {**row, "title": "OpenAI Astra model release", "evidence_reason": "OpenAI model release",
                 "event_identity_tokens": ["astra"], "entities": ["OpenAI", "Astra"]}
        self.assertFalse(coverage._signals_related(row, other))
        self.assertFalse(coverage._rejection_matches_signal({"title": candidate["title"], "reason": "OpenAI model release outside window"}, row))

    def test_current_quality_gate_rechecks_old_complete_without_repaying(self):
        prior = {"publication_date": "2026-09-05", "audit_status": "complete", "audit_state": "completed_usable",
                 "web_search_performed": True, "api": {"status": "completed"},
                 "checked_directions": list(coverage.AUDIT_DIRECTION_IDS), "candidate_pool_before": {"total": 9},
                 "retrieval_quality": {"status": "complete", "required_signal_count": 0}, "attempts": []}
        self.assertTrue(coverage.completed_prior_audit(prior))
        with patch.object(coverage, "_required_signals", return_value=signals()):
            self.assertFalse(coverage._quality_aware_completed_prior(prior))

    def test_real_wrapper_adds_recoverable_date_to_engine_checkpoint(self):
        base = {"audit_status": "complete", "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
                "attempts": [], "search_budget": {"maximum_calls": 7, "completed_calls": 6, "remaining_calls": 1}}
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "coverage-audit.json"
            with patch.object(coverage, "_required_signals", return_value=signals()), patch.object(coverage, "_V8_EXECUTE", return_value=base), patch.object(coverage._runtime, "_report_path", return_value=checkpoint), patch.object(coverage._runtime, "_policy_audit_request", side_effect=TimeoutError("unknown")):
                coverage.execute_audit_plan(api_key="unused", model="unused", template="", publication_date="2026-09-05",
                    search_window=WINDOW, missing_total=1, maximum_web_search_calls=7, existing_candidates=[], archive={})
            saved = json.loads(checkpoint.read_text())
            self.assertEqual(saved["publication_date"], "2026-09-05")
            self.assertEqual(saved["search_window"], WINDOW)
            self.assertTrue(recovery.coverage_audit_was_attempted(saved))

    def test_recovery_restores_only_selected_lineage_and_window(self):
        for sibling_only, mismatch in ((False, False), (True, False), (False, True)):
            with self.subTest(sibling=sibling_only, mismatch=mismatch), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                selected = root / "runA" / "2026-09-05"
                selected.mkdir(parents=True)
                target = root / "target"; target.mkdir()
                (target / "candidates.json").write_text(json.dumps({"search_window": WINDOW}))
                (target / "primary-recall.json").write_text(json.dumps(F["primary"]))
                diag = root / ("runB" if sibling_only else "runA") / "production-daily"; diag.mkdir(parents=True)
                report = copy.deepcopy(F["source_freshness"])
                if mismatch: report["runs"][0]["search_window"]["end_at"] = "2026-09-06T00:00:00Z"
                (diag / "source-freshness-2026-09-05.json").write_text(json.dumps(report))
                out = root / "restored" / "recovery.json"
                result = recovery._restore_source_resolution_evidence(recovery_root=root, target_dir=target,
                    publication_date="2026-09-05", report_path=out, selected_source=selected)
                self.assertEqual(result["status"], "unavailable" if sibling_only or mismatch else "restored")
                if result["status"] == "restored":
                    self.assertEqual(json.loads(Path(result["target"]).read_text()), report)


class OpenAIExactPublicationProofTests(unittest.TestCase):
    def proof(self, *, html=None, rss=None, url=None, final=None, feed_final=None):
        body = F["official_proof"]["html_extract"] if html is None else html
        feed = F["official_proof"]["rss_extract"] if rss is None else rss
        url = url or F["official_url"]
        calls = []
        def fetch(endpoint):
            calls.append(endpoint)
            return feed, feed_final or endpoint, 200
        result = first_party_evidence(body, url, final or url, fetch)
        return result, calls

    def test_exact_feed_time_and_visible_date_prove_same_article(self):
        result, calls = self.proof()
        self.assertEqual(result.published_at.isoformat(), F["official_proof"]["published_at"])
        self.assertEqual(calls, [OPENAI_NEWS_FEED])

    def test_wrong_article_host_query_fragment_and_redirect_never_borrow(self):
        for url, final in (
            ("https://openai.com/index/wrong", None),
            ("https://openai.com.evil.test/index/daybreak-for-frontline-defenders", None),
            (F["official_url"] + "?x=1", None), (F["official_url"] + "#x", None),
            (F["official_url"], "https://openai.com/index/wrong"),
        ):
            with self.subTest(url=url, final=final): self.assertIsNone(self.proof(url=url, final=final)[0])
        self.assertIsNone(self.proof(feed_final="https://openai.com/other.xml")[0])

    def test_conflicting_ambiguous_and_unaware_feed_proof_stays_unverified(self):
        rss = F["official_proof"]["rss_extract"]
        for altered in (rss.replace("03 Sep", "04 Sep"), rss.replace(" GMT", ""),
                        rss.replace("13:15:00 GMT", "invalid"), rss.replace("<item>", "<item>", 1).replace("</channel>", rss[rss.index("<item>"):rss.index("</item>")+7]+"</channel>")):
            with self.subTest(rss=altered): self.assertIsNone(self.proof(rss=altered)[0])

    def test_arbitrary_body_date_is_not_publication_proof(self):
        result, calls = self.proof(html="<p>September 3, 2026</p>")
        self.assertIsNone(result); self.assertEqual(calls, [])

    def test_generic_stale_metadata_and_stale_event_keep_priority(self):
        raw = copy.deepcopy(F["daybreak"]); raw["primary_source"]["url"] = F["official_url"]
        for stale_event in (False, True):
            candidate = copy.deepcopy(raw); calls = []
            if stale_event: candidate.update(event_at="2026-08-01T12:00:00Z", event_time_precision="datetime", event_date="2026-08-01")
            def fetch(url):
                calls.append(url)
                return '<meta property="article:published_time" content="2026-08-01T12:00:00Z">', url, 200
            result = freshness.verify_candidate(candidate, start_at=datetime.fromisoformat(WINDOW["start_at"]),
                end_at=datetime.fromisoformat(WINDOW["end_at"]), fetcher=fetch)
            self.assertEqual(result["status"], "excluded_event_freshness_stale" if stale_event else "excluded_outside_window")
            self.assertEqual(calls, [] if stale_event else [F["official_url"]])


if __name__ == "__main__": unittest.main()
