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


primary = load("p3b_replacement_roles_primary", "primary_recall_search.py")
binder = load("p3b_replacement_roles_binder", "weak_source_exact_binding_v2.py")


class P3bReplacementRoleTests(unittest.TestCase):
    @staticmethod
    def rejection(title: str) -> dict:
        return {
            "title": title,
            "url": "https://huggingnews.com/ai/deepseek-v41-flash",
            "reason_code": "weak_source",
            "reason": "Weak-source product event awaiting authoritative exact binding.",
        }

    @staticmethod
    def candidate(title: str) -> dict:
        return {
            "title": title,
            "organization": "DeepSeek",
            "event_type": "release",
            "recommendation": "include",
            "verification_status": "verified",
            "freshness_status": "new_event",
            "primary_source": {
                "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            },
        }

    def signal(self, title: str) -> dict:
        rows = primary.collect_unresolved_signals(
            [{
                "direction_id": "independent_missing_events",
                "model_rejections": [self.rejection(title)],
            }]
        )
        self.assertEqual(len(rows), 1)
        return rows[0]

    def bind(self, candidate_title: str, signal: dict, page_title: str):
        candidate = self.candidate(candidate_title)
        return binder.candidate_exact_binding(
            candidate,
            signal,
            authoritative_domains=("deepseek.com",),
            authoritative_page_surface=page_title,
            authoritative_final_url=candidate["primary_source"]["url"],
        )

    def test_primary_anchor_appearance_order_does_not_define_replacement_roles(self) -> None:
        signal = self.signal(
            "DeepSeek replaces older model: V4.1 Flash replaces V4 Pro"
        )
        self.assertEqual(
            signal["product_version_anchors"],
            ["V4.1 Flash", "V4 Pro"],
        )
        self.assertEqual(signal["lifecycle_action_anchors"], ["replace"])
        self.assertEqual(
            binder._replacement_roles(signal),
            (("V4 Pro", "V4.1 Flash"), "replacement_roles_from_signal_claim"),
        )

    def test_new_before_old_signal_accepts_same_semantic_direction(self) -> None:
        signal = self.signal(
            "DeepSeek replaces older model: V4.1 Flash replaces V4 Pro"
        )
        self.assertEqual(
            self.bind(
                "DeepSeek V4.1 Flash replaces V4 Pro",
                signal,
                "DeepSeek V4.1 Flash replaces V4 Pro",
            ),
            (True, "exact_authoritative_page_binding"),
        )

    def test_new_before_old_signal_rejects_reverse_replacement(self) -> None:
        signal = self.signal(
            "DeepSeek replaces older model: V4.1 Flash replaces V4 Pro"
        )
        ok, reason = self.bind(
            "DeepSeek V4 Pro replaces V4.1 Flash",
            signal,
            "DeepSeek V4 Pro replaces V4.1 Flash",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "replacement_direction_mismatch")

    def test_old_before_new_signal_still_accepts_same_direction(self) -> None:
        signal = self.signal("DeepSeek replaces V4 Pro with V4.1 Flash")
        self.assertEqual(
            signal["product_version_anchors"],
            ["V4 Pro", "V4.1 Flash"],
        )
        self.assertEqual(
            binder._replacement_roles(signal),
            (("V4 Pro", "V4.1 Flash"), "replacement_roles_from_signal_claim"),
        )
        self.assertEqual(
            self.bind(
                "DeepSeek V4.1 Flash replaces V4 Pro",
                signal,
                "DeepSeek V4 Pro is replaced by V4.1 Flash",
            ),
            (True, "exact_authoritative_page_binding"),
        )

    def test_ambiguous_signal_direction_fails_closed(self) -> None:
        signal = self.signal(
            "DeepSeek replaces models: V4.1 Flash replaces V4 Pro; V4 Pro replaces V4.1 Flash"
        )
        self.assertEqual(signal["organization"], "DeepSeek")
        self.assertIsNone(binder._replacement_roles(signal)[0])
        ok, reason = self.bind(
            "DeepSeek V4.1 Flash replaces V4 Pro",
            signal,
            "DeepSeek V4.1 Flash replaces V4 Pro",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "replacement_direction_mismatch")

    def test_permuting_anchor_array_does_not_change_inferred_roles(self) -> None:
        signal = self.signal("DeepSeek replaces V4 Pro with V4.1 Flash")
        permuted = copy.deepcopy(signal)
        permuted["product_version_anchors"] = list(
            reversed(permuted["product_version_anchors"])
        )
        self.assertEqual(
            binder._replacement_roles(signal),
            binder._replacement_roles(permuted),
        )
        for current in (signal, permuted):
            self.assertEqual(
                self.bind(
                    "DeepSeek V4.1 Flash replaces V4 Pro",
                    current,
                    "DeepSeek V4.1 Flash replaces V4 Pro",
                ),
                (True, "exact_authoritative_page_binding"),
            )


if __name__ == "__main__":
    unittest.main()
