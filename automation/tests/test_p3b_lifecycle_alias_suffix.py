from __future__ import annotations

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


binder = load("p3b_lifecycle_alias_suffix_binder", "weak_source_exact_binding_v2.py")


class P3bLifecycleAliasSuffixTests(unittest.TestCase):
    @staticmethod
    def signal(action: str, *, anchor: str = "V4.1 Flash") -> dict:
        return {
            "signal_id": f"p2-{action}",
            "title": f"DeepSeek {anchor} {action}",
            "organization": "DeepSeek",
            "product_version_anchors": [anchor],
            "lifecycle_action_anchors": [action],
            "source_provenance": {"url": "https://weak.example/deepseek"},
        }

    @staticmethod
    def candidate(title: str, event_type: str) -> dict:
        return {
            "title": title,
            "organization": "DeepSeek",
            "event_type": event_type,
            "recommendation": "include",
            "verification_status": "verified",
            "freshness_status": "new_event",
            "primary_source": {
                "url": "https://www.deepseek.com/en/news/v4-1-flash/",
            },
        }

    def bind(self, signal: dict, title: str, event_type: str = "release"):
        candidate = self.candidate(title, event_type)
        return binder.candidate_exact_binding(
            candidate,
            signal,
            authoritative_domains=("deepseek.com",),
            authoritative_page_surface=title,
            authoritative_final_url=candidate["primary_source"]["url"],
        )

    def test_general_availability_primary_canonical_alias_binds(self) -> None:
        signal = self.signal("general_availability")
        title = "DeepSeek V4.1 Flash is generally available"
        self.assertEqual(
            self.bind(signal, title, "general availability"),
            (True, "exact_authoritative_page_binding"),
        )

    def test_general_availability_alias_keeps_negation_fail_closed(self) -> None:
        signal = self.signal("general_availability")
        candidate = self.candidate(
            "DeepSeek V4.1 Flash is generally available",
            "general availability",
        )
        ok, reason = binder.candidate_exact_binding(
            candidate,
            signal,
            authoritative_domains=("deepseek.com",),
            authoritative_page_surface="DeepSeek V4.1 Flash is not generally available",
            authoritative_final_url=candidate["primary_source"]["url"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "authoritative_page_lifecycle_negated")

    def test_unknown_adjacent_variant_suffix_is_not_exact_anchor(self) -> None:
        signal = self.signal("launch")
        ok, reason = binder.exact_event_identity(
            "DeepSeek launches V4.1 Flash Thinking",
            signal,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "version_identity_mismatch")

    def test_numeric_adjacent_variant_suffix_is_not_exact_anchor(self) -> None:
        signal = self.signal("launch")
        ok, reason = binder.exact_event_identity(
            "DeepSeek launches V4.1 Flash 2",
            signal,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "version_identity_mismatch")

    def test_normal_prose_after_exact_anchor_remains_valid(self) -> None:
        signal = self.signal("launch")
        self.assertEqual(
            binder.exact_event_identity(
                "DeepSeek launches V4.1 Flash for developers",
                signal,
            ),
            (True, "exact_event_identity"),
        )


if __name__ == "__main__":
    unittest.main()
