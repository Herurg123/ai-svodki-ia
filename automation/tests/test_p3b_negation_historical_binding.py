from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


binder = load("p3b_negation_historical_binder", "weak_source_exact_binding_v2.py")


class P3bNegationHistoricalBindingTests(unittest.TestCase):
    @staticmethod
    def signal(*, action: str = "replace", anchors: list[str] | None = None) -> dict:
        return {
            "signal_id": "weak-source-p1-negation-history",
            "organization": "DeepSeek",
            "product_version_anchors": anchors or ["V4 Pro", "V4.1 Flash"],
            "lifecycle_action_anchors": [action],
            "source_provenance": {
                "url": "https://huggingnews.com/ai/deepseek-v41-flash",
            },
        }

    @staticmethod
    def candidate(title: str, *, event_type: str = "release") -> dict:
        return {
            "title": title,
            "organization": "DeepSeek",
            "event_type": event_type,
            "recommendation": "include",
            "verification_status": "verified",
            "freshness_status": "new_event",
            "primary_source": {
                "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            },
        }

    @staticmethod
    def html(title: str, *paragraphs: str) -> str:
        body = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
        return (
            "<html><head>"
            f"<title>{title}</title>"
            f"<meta property='og:title' content='{title}'>"
            "</head><body>"
            f"<h1>{title}</h1>{body}"
            "</body></html>"
        )

    @property
    def domains(self) -> tuple[str, ...]:
        return ("deepseek.com",)

    def bind(self, candidate: dict, signal: dict, page_surface: str):
        return binder.candidate_exact_binding(
            candidate,
            signal,
            authoritative_domains=self.domains,
            authoritative_page_surface=page_surface,
            authoritative_final_url=candidate["primary_source"]["url"],
        )

    def test_negated_candidate_lifecycle_is_not_positive_proof(self) -> None:
        signal = self.signal(action="launch", anchors=["V4.1 Flash"])
        candidate = self.candidate(
            "DeepSeek did not launch V4.1 Flash",
            event_type="launch",
        )
        ok, reason = self.bind(
            candidate,
            signal,
            "DeepSeek did not launch V4.1 Flash",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "lifecycle_negated")

    def test_negated_authoritative_page_does_not_bind_positive_card(self) -> None:
        signal = self.signal(action="ga", anchors=["V4.1 Flash"])
        candidate = self.candidate(
            "DeepSeek announces general availability of V4.1 Flash",
            event_type="general availability",
        )
        ok, reason = self.bind(
            candidate,
            signal,
            "DeepSeek V4.1 Flash is not generally available",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "authoritative_page_lifecycle_negated")

    def test_current_page_with_only_historical_exact_event_does_not_bind(self) -> None:
        signal = self.signal()
        candidate = self.candidate("DeepSeek replaces V4 Pro with V4.1 Flash")
        html = self.html(
            "DeepSeek launches R2",
            "Previously, DeepSeek replaced V4 Pro with V4.1 Flash during the prior lineup.",
            "R2 is the current product announcement.",
        )
        surface = binder.extract_authoritative_event_surface(html)
        ok, reason = self.bind(candidate, signal, surface)
        self.assertFalse(ok)
        self.assertEqual(reason, "authoritative_page_historical_event_context")

    def test_past_perfect_exact_event_is_historical_context(self) -> None:
        signal = self.signal(action="launch", anchors=["V4.1 Flash"])
        candidate = self.candidate("DeepSeek launches V4.1 Flash", event_type="launch")
        page = "DeepSeek announces R2. DeepSeek had launched V4.1 Flash before the R2 program."
        ok, reason = self.bind(candidate, signal, page)
        self.assertFalse(ok)
        self.assertEqual(reason, "authoritative_page_historical_event_context")

    def test_current_exact_assertion_survives_separate_historical_context(self) -> None:
        signal = self.signal()
        candidate = self.candidate("DeepSeek replaces V4 Pro with V4.1 Flash")
        html = self.html(
            "DeepSeek replaces V4 Pro with V4.1 Flash",
            "Previously, DeepSeek previewed V4.1 Flash for selected users.",
            "The replacement is the current announcement.",
        )
        surface = binder.extract_authoritative_event_surface(html)
        self.assertIn(" | ", surface)
        self.assertEqual(
            self.bind(candidate, signal, surface),
            (True, "exact_authoritative_page_binding"),
        )

    def test_event_identity_requires_one_local_claim_not_bag_of_words(self) -> None:
        signal = self.signal(action="launch", anchors=["V4.1 Flash"])
        surface = "DeepSeek launches a new model | V4.1 Flash documentation"
        ok, reason = binder.exact_event_identity(surface, signal)
        self.assertFalse(ok)
        self.assertIn(reason, {"exact_event_claim_missing", "lifecycle_identity_mismatch"})


if __name__ == "__main__":
    unittest.main()
