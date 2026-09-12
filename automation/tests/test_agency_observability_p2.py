from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agency_discovery_rescue_v5 as active
import agency_discovery_rescue_v5_base as v5_base
import agency_discovery_rescue_v6 as v6


PUBLICATION_DATE = "2026-09-11"
WINDOW = {
    "start_date": "2026-09-10",
    "end_date": "2026-09-11",
    "start_at": "2026-09-10T01:04:18+00:00",
    "end_at": "2026-09-11T01:05:09+00:00",
}


def api_metadata(sources_marker="empty") -> dict:
    action = {"type": "search", "query": v6.AGENCY_DISCOVERY_RESCUE_QUERY}
    if sources_marker == "null":
        action["sources"] = None
    elif sources_marker == "empty":
        action["sources"] = []
    elif sources_marker == "nonempty":
        action["sources"] = [{"url": "https://www.reuters.com/example"}]
    elif sources_marker == "malformed":
        action["sources"] = "not-a-list"
    elif sources_marker != "missing":
        raise AssertionError(sources_marker)
    return {
        "web_search_calls_completed": 1,
        "actual_queries": [v6.AGENCY_DISCOVERY_RESCUE_QUERY],
        "web_search_call_items": [
            {
                "id": "search-1",
                "status": "completed",
                "action_type": "search",
                "action": action,
            }
        ],
    }


def response_payload() -> dict:
    return {
        "status": "complete_with_gaps",
        "error_message": None,
        "direction_id": v6.AGENCY_DISCOVERY_RESCUE_DIRECTION,
        "candidates": [],
        "rejections": [],
        "notes": "fixture zero-result response",
    }


class FakeAction:
    def __init__(self, sources_marker="empty"):
        self.type = "search"
        self.query = v6.AGENCY_DISCOVERY_RESCUE_QUERY
        self._sources_marker = sources_marker

    def model_dump(self):
        action = {"type": self.type, "query": self.query}
        if self._sources_marker == "null":
            action["sources"] = None
        elif self._sources_marker == "empty":
            action["sources"] = []
        elif self._sources_marker == "nonempty":
            action["sources"] = [{"url": "https://www.reuters.com/example"}]
        elif self._sources_marker == "malformed":
            action["sources"] = "broken"
        elif self._sources_marker != "missing":
            raise AssertionError(self._sources_marker)
        return action


class FakeItem:
    type = "web_search_call"
    status = "completed"
    id = "search-1"

    def __init__(self, sources_marker="empty"):
        self.action = FakeAction(sources_marker)

    def model_dump(self):
        return {
            "type": self.type,
            "status": self.status,
            "id": self.id,
            "action": self.action.model_dump(),
        }


class FakeResponse:
    def __init__(self, output_text: str, *, sources_marker="empty"):
        self.id = "resp-fixture"
        self.status = "completed"
        self.model = "test-model"
        self.output_text = output_text
        self.output = [FakeItem(sources_marker)]
        self.usage = {"input_tokens": 10, "output_tokens": 20}
        self.error = None
        self.incomplete_details = None

    def model_dump(self):
        return {
            "id": self.id,
            "status": self.status,
            "model": self.model,
            "output_text": self.output_text,
            "output": [item.model_dump() for item in self.output],
            "usage": self.usage,
            "error": self.error,
            "incomplete_details": self.incomplete_details,
        }


class FakeOpenAI:
    def __init__(self, *, api_key, timeout, max_retries):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.responses = types.SimpleNamespace(create=lambda **kwargs: None)


class AgencyObservabilityP2Tests(unittest.TestCase):
    def test_preserved_v5_blob_surface_and_active_shim(self):
        self.assertEqual(v5_base.AGENCY_DISCOVERY_RESCUE_VERSION, 5)
        self.assertEqual(active.AGENCY_DISCOVERY_RESCUE_VERSION, 6)
        self.assertEqual(active.AGENCY_DISCOVERY_RESCUE_QUERY, v5_base.AGENCY_DISCOVERY_RESCUE_QUERY)
        self.assertEqual(active.MAXIMUM_SEARCH_OPERATIONS, 1)
        self.assertTrue(callable(active._persist_report))
        self.assertTrue(callable(active.neutral_query))

    def test_request_contract_is_observability_only(self):
        contract = v6._request_contract(model="test-model", prompt="fixture prompt")
        self.assertEqual(contract["query"], v5_base.AGENCY_DISCOVERY_RESCUE_QUERY)
        self.assertEqual(contract["tools"], [v5_base.v3._web_search_tool()])
        self.assertEqual(contract["max_tool_calls"], v5_base.v3.MAXIMUM_TOOL_CALLS)
        self.assertEqual(contract["include"], ["web_search_call.action.sources"])
        self.assertEqual(contract["reasoning"], {"effort": "medium"})
        self.assertEqual(contract["max_output_tokens"], 5000)
        self.assertEqual(contract["sdk_max_retries"], 2)
        self.assertFalse(any("key" in key.casefold() for key in contract))

    def test_source_metadata_states_are_not_collapsed(self):
        expected = {
            "missing": "missing",
            "null": "null",
            "empty": "empty",
            "nonempty": "nonempty",
            "malformed": "malformed",
        }
        for marker, state in expected.items():
            with self.subTest(marker=marker):
                diagnostic = v6.classify_source_metadata(api_metadata(marker))
                self.assertEqual(diagnostic["state"], state)
        self.assertEqual(v6.classify_source_metadata({})["state"], "unknown")

    def test_raw_response_is_saved_before_parse_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            output = root / "diag"
            artifact.mkdir()
            output.mkdir()
            runner = v6._instrumented_search_runner(
                artifact_dir=artifact,
                output_root=output,
                publication_date=PUBLICATION_DATE,
            )
            fake_openai = types.ModuleType("openai")
            fake_openai.OpenAI = FakeOpenAI
            response = FakeResponse("{not valid json", sources_marker="null")
            with mock.patch.dict(sys.modules, {"openai": fake_openai}):
                with mock.patch.object(v6, "call_with_usage", return_value=response):
                    with self.assertRaises(v6.v3.AgencyDiscoveryResponseError):
                        runner(api_key="secret-test-key", model="test-model", prompt="fixture prompt")

            capture = json.loads(
                (artifact / "agency-discovery-rescue-transport.json").read_text(encoding="utf-8")
            )
            self.assertEqual(capture["transport_state"], "response_saved")
            self.assertEqual(capture["response_parse_status"], "response_error")
            self.assertTrue(capture["raw_response_saved_before_parse"])
            self.assertIn("raw", capture["response"])
            serialized = json.dumps(capture, ensure_ascii=False)
            self.assertNotIn("secret-test-key", serialized)
            self.assertEqual(
                capture["request_contract"]["query"],
                v5_base.AGENCY_DISCOVERY_RESCUE_QUERY,
            )

    def test_successful_response_capture_and_empty_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            output = root / "diag"
            artifact.mkdir()
            output.mkdir()
            runner = v6._instrumented_search_runner(
                artifact_dir=artifact,
                output_root=output,
                publication_date=PUBLICATION_DATE,
            )
            fake_openai = types.ModuleType("openai")
            fake_openai.OpenAI = FakeOpenAI
            response = FakeResponse(json.dumps(response_payload()), sources_marker="empty")
            with mock.patch.dict(sys.modules, {"openai": fake_openai}):
                with mock.patch.object(v6, "call_with_usage", return_value=response):
                    payload, metadata = runner(
                        api_key="secret-test-key",
                        model="test-model",
                        prompt="fixture prompt",
                    )
            self.assertEqual(payload["candidates"], [])
            self.assertEqual(v6.classify_source_metadata(metadata)["state"], "empty")
            capture = json.loads(
                (artifact / "agency-discovery-rescue-transport.json").read_text(encoding="utf-8")
            )
            self.assertEqual(capture["response_parse_status"], "parsed_valid")
            self.assertTrue(capture["raw_response_saved_before_parse"])

    def test_observability_separates_route_validation_dedupe_and_cap(self):
        report = {
            "executed": True,
            "state": "completed_no_addition",
            "raw_count": 7,
            "validated_count": 4,
            "accepted_count": 0,
            "added_count": 0,
            "model_rejections": [{"reason_code": "weak_source"}],
            "api": api_metadata("nonempty"),
            "rejections": [
                {"reason_code": "non_direct_reuters_ap_source"},
                {"reason_code": "archive_exact_url_duplicate"},
                {"reason_code": "duplicate_existing_event"},
                {"errors": ["кандидат находится вне редакционного окна"]},
                {"errors": ["primary_source.title должен быть непустым"]},
                {"errors": ["дубликат существующего кандидата"]},
                {"errors": ["достигнут maximum_candidates"]},
            ],
        }
        diagnostic = v6.build_observability(report, None)
        self.assertEqual(diagnostic["model"]["candidate_count"], 7)
        self.assertEqual(diagnostic["model"]["rejection_count"], 1)
        self.assertEqual(diagnostic["post_model_route"]["pre_merge_eligible_count"], 4)
        self.assertEqual(diagnostic["post_model_route"]["host_rejection_count"], 1)
        self.assertEqual(diagnostic["merge_validation"]["post_validation_count"], 2)
        self.assertEqual(diagnostic["merge_validation"]["window_rejection_count"], 1)
        self.assertEqual(diagnostic["merge_validation"]["schema_rejection_count"], 1)
        self.assertEqual(diagnostic["merge_validation"]["cap_rejection_count"], 1)
        self.assertEqual(diagnostic["source_metadata"]["state"], "nonempty")
        self.assertEqual(diagnostic["transport"]["state"], "legacy_or_injected_unobserved")

    def test_injected_runner_remains_at_most_once_across_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            output = root / "diag"
            archive = root / "archive.json"
            artifact.mkdir()
            output.mkdir()
            (artifact / "candidates.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "search_window": WINDOW,
                        "coverage": [],
                        "candidates": [],
                    }
                ),
                encoding="utf-8",
            )
            (artifact / "primary-recall.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "directions": [
                            {
                                "direction_id": "major_agencies",
                                "status": "complete",
                                "raw_candidates": [],
                                "accepted_count": 0,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            archive.write_text('{"items": []}\n', encoding="utf-8")
            calls = 0

            def once(**kwargs):
                nonlocal calls
                calls += 1
                self.assertEqual(kwargs["model"], "test-model")
                return response_payload(), api_metadata("empty")

            first = v6.run_agency_discovery_rescue(
                artifact_dir=artifact,
                archive_path=archive,
                publication_date=PUBLICATION_DATE,
                api_key="test-key",
                model="test-model",
                search_runner=once,
                output_root=output,
            )
            self.assertEqual(calls, 1)
            self.assertEqual(first["version"], 6)
            self.assertEqual(first["state"], "completed_no_addition")
            self.assertEqual(first["search_operation_count_contribution"], 1)
            self.assertEqual(first["source_metadata_state"], "empty")
            self.assertEqual(
                first["observability"]["transport"]["state"],
                "legacy_or_injected_unobserved",
            )

            def forbidden(**_kwargs):
                raise AssertionError("completed rescue must not search twice")

            resumed = v6.run_agency_discovery_rescue(
                artifact_dir=artifact,
                archive_path=archive,
                publication_date=PUBLICATION_DATE,
                api_key="test-key",
                model="test-model",
                search_runner=forbidden,
                output_root=output,
            )
            self.assertEqual(calls, 1)
            self.assertTrue(resumed["resumed"])
            self.assertEqual(resumed["search_operation_count_contribution"], 1)
            self.assertEqual(resumed["version"], 6)


if __name__ == "__main__":
    unittest.main()
