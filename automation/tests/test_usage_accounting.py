from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import usage_ledger as ledger
import usage_observer as observer

DATE = "2026-09-05"


def response(identity="resp_a", *, inp=1000, out=100):
    return {"id": identity, "model": "gpt-5.6-terra", "status": "completed",
            "usage": {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
                      "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 200}},
            "output": [{"type": "web_search_call", "status": "completed", "action": {"type": "search"}},
                       {"type": "web_search_call", "status": "completed", "action": {"type": "open_page"}}]}


class UsageAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")
        return target

    def build(self):
        return ledger.build_ledger([self.root], DATE)

    def test_exact_transport_arguments_identity_and_no_extra_call(self):
        original = response()
        seen = []
        def callback(**kwargs):
            seen.append(copy.deepcopy(kwargs))
            return original
        kwargs = {"model": "gpt-5.6-terra", "input": "PRIVATE_PROMPT", "api_key": "PRIVATE_KEY", "store": False}
        with patch.dict(os.environ, {"AI_DIGEST_USAGE_DIR": str(self.root / "usage-events"),
                                    "AI_DIGEST_PUBLICATION_DATE": DATE}):
            result = observer.call_with_usage("primary", callback, **kwargs)
        self.assertIs(result, original)
        self.assertEqual(seen, [kwargs])
        saved = next((self.root / "usage-events").glob("*.json")).read_text()
        self.assertNotIn("PRIVATE_", saved)
        report = self.build()
        self.assertEqual(report["stages"]["primary"]["search_operations_observed"], 1)
        self.assertEqual(report["stages"]["primary"]["tokens_observed"]["input_tokens"], 1000)

    def test_exception_not_retried_or_replaced(self):
        error = RuntimeError("PRIVATE_ERROR")
        calls = []
        def callback(**kwargs):
            calls.append(kwargs)
            raise error
        with patch.dict(os.environ, {"AI_DIGEST_USAGE_DIR": str(self.root / "usage-events"),
                                    "AI_DIGEST_PUBLICATION_DATE": DATE}):
            with self.assertRaises(RuntimeError) as got:
                observer.call_with_usage("hybrid", callback, model="gpt-5.6-terra")
        self.assertIs(got.exception, error)
        self.assertEqual(len(calls), 1)
        report = self.build()
        self.assertEqual(report["stages"]["hybrid"]["unknown_cost_calls"], 1)
        self.assertIn("api_outcome_unknown", report["records"][0]["accounting_gaps"])
        self.assertNotIn("PRIVATE_ERROR", next((self.root / "usage-events").glob("*.json")).read_text())

    def test_unwritable_observer_never_discards_paid_result(self):
        block = self.root / "file-not-directory"
        block.write_text("block")
        original = response()
        calls = []
        with patch.dict(os.environ, {"AI_DIGEST_USAGE_DIR": str(block)}), contextlib.redirect_stderr(io.StringIO()):
            result = observer.call_with_usage("primary", lambda **kw: (calls.append(kw), original)[1], model="gpt-5.6-terra")
        self.assertIs(result, original)
        self.assertEqual(len(calls), 1)

    def test_duplicate_response_and_navigation_not_search(self):
        self.write("primary-recall.json", {"publication_date": DATE, "response": response()})
        self.write("image/copy/run-info.json", {"research": {"response": response()}})
        report = self.build()
        self.assertEqual(report["unique_calls"], 1)
        self.assertEqual(report["stages"]["primary"]["search_operations_observed"], 1)
        self.assertAlmostEqual(report["estimated_observed_usd"], 0.01312)

    def test_foreign_day_path_and_explicit_date_ignored(self):
        self.write("2026-09-04/run-info.json", {"editorial": {"response": response("resp_old")}})
        self.write("primary-recall-other.json", {"publication_date": "2026-09-04", "response": response("resp_old2")})
        self.write("primary-recall.json", {"publication_date": DATE, "response": response()})
        self.assertEqual(self.build()["unique_calls"], 1)

    def test_recovery_chain_and_repeated_reducer_do_not_double_count(self):
        self.write("primary-recall.json", {"publication_date": DATE, "response": response()})
        first = self.build()
        (self.root / "primary-recall.json").unlink()
        self.write("recovered/usage-ledger.json", first)
        self.write("coverage-audit.json", {"publication_date": DATE, "response": response("resp_b")})
        second = self.build()
        self.assertEqual(second["unique_calls"], 2)
        self.write("usage-ledger.json", second)
        self.assertEqual(self.build()["unique_calls"], 2)

    def test_conflicting_copies_do_not_receive_cost_certainty(self):
        self.write("primary-recall.json", {"response": response()})
        self.write("coverage-audit.json", {"response": response(inp=2000)})
        record = self.build()["records"][0]
        self.assertIn("conflicting_copies", record["accounting_gaps"])
        self.assertIsNone(record["model_cost_estimate_usd"])

    def test_missing_cache_unknown_model_and_malformed_json_are_visible(self):
        r = response()
        del r["usage"]["input_tokens_details"]
        r["model"] = "future-model"
        self.write("primary-recall.json", {"response": r})
        bad = self.root / "coverage-audit.json"
        bad.write_text("{broken")
        report = self.build()
        self.assertEqual(report["accounting_status"], "partial")
        self.assertIsNone(report["records"][0]["model_cost_estimate_usd"])
        self.assertTrue(any(s.startswith("unreadable:") for s in report["accounting_gaps"]))

    def test_image_journal_and_report_share_identity_without_provider_id(self):
        r = {"created": 123, "usage": {"input_tokens": 20, "output_tokens": 100,
             "total_tokens": 120, "input_tokens_details": {"text_tokens": 20, "image_tokens": 0}}}
        metadata = {}
        with patch.dict(os.environ, {"AI_DIGEST_USAGE_DIR": str(self.root / "usage-events"),
                                    "AI_DIGEST_PUBLICATION_DATE": DATE}):
            observer.call_with_usage("image", lambda **kw: r, usage_model="gpt-image-2",
                                     usage_kind="image", usage_identity="local-image-1", usage_metadata=metadata)
        self.write("image-api-response.json", {"publication_date": DATE, "request_id": "local-image-1",
                                                "usage_attempt_id": metadata["attempt_id"],
                                                "model": "gpt-image-2", "response": r})
        report = self.build()
        self.assertEqual(report["unique_calls"], 1)
        self.assertAlmostEqual(report["stages"]["image"]["estimated_observed_usd"], 0.0031)

    def test_separate_image_calls_with_identical_payloads_and_release_id(self):
        payload = {"created": 123, "usage": {"input_tokens": 20, "output_tokens": 100,
                   "total_tokens": 120, "input_tokens_details": {"text_tokens": 20, "image_tokens": 0}}}
        for index in range(2):
            metadata = {}
            with patch.dict(os.environ, {"AI_DIGEST_USAGE_DIR": str(self.root / "usage-events"),
                                        "AI_DIGEST_PUBLICATION_DATE": DATE}):
                observer.call_with_usage("image", lambda **kw: payload, usage_model="gpt-image-2",
                                         usage_kind="image", usage_identity="same-release", usage_metadata=metadata)
            saved = {"publication_date": DATE, "request_id": "same-release",
                     "usage_attempt_id": metadata["attempt_id"], "model": "gpt-image-2", "response": payload}
            self.write(f"run-{index}/image-api-response.json", saved)
            self.write(f"copied-{index}/image-api-response.json", saved)
        first = self.build()
        self.assertEqual(first["stages"]["image"]["unique_calls"], 2)
        self.assertAlmostEqual(first["stages"]["image"]["estimated_observed_usd"], .0062)
        self.write("recovered/usage-ledger.json", first)
        self.assertEqual(self.build()["stages"]["image"], first["stages"]["image"])

    def test_legacy_image_without_provider_or_attempt_id_stays_uncertain(self):
        payload = {"request_id": "same-release", "model": "gpt-image-2", "response": {
            "created": 123, "usage": {"input_tokens": 20, "output_tokens": 100,
            "input_tokens_details": {"text_tokens": 20, "image_tokens": 0}}}}
        self.write("image-api-response.json", payload)
        self.write("copy/image-api-response.json", payload)
        report = self.build()
        self.assertEqual(report["unique_calls"], 1)
        self.assertIn("provider_identity_missing", report["records"][0]["accounting_gaps"])

    def test_interrupted_image_snapshot_resolves_when_same_attempt_finishes(self):
        started = {"usage_event_version": 1, "attempt_id": "uuid-one", "kind": "image",
                   "stage": "image", "state": "started", "model": "gpt-image-2", "usage": None}
        self.write("usage-events/a-started.json", started)
        completed = dict(started, state="response_received", usage={"input_tokens": 20, "output_tokens": 100,
                         "input_tokens_details": {"text_tokens": 20, "image_tokens": 0}})
        self.write("usage-events/z-completed.json", completed)
        report = self.build()
        self.assertEqual(report["unique_calls"], 1)
        self.assertEqual(report["records"][0]["state"], "response_received")
        self.assertNotIn("api_outcome_unknown", report["records"][0]["accounting_gaps"])

    def test_long_context_boundary_and_invalid_partition(self):
        for inp, expected in [(272000, (271700*2+100*.2+200*2.5+100*12)/1e6),
                              (272001, ((271701*2+100*.2+200*2.5)*2+100*18)/1e6)]:
            record = ledger._observation(response(inp=inp), "primary-recall.json", "")
            self.assertAlmostEqual(ledger.cost(record)[0], expected)
        record = ledger._observation(response(inp=250), "primary-recall.json", "")
        self.assertIsNone(ledger.cost(record)[0])


if __name__ == "__main__":
    unittest.main()
