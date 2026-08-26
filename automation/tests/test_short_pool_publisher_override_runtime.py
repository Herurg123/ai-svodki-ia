from __future__ import annotations

# Regression coverage for the deterministic short-pool publisher override.

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy import validate_diversity_overrides  # noqa: E402
from editorial_policy_runtime import wrap_editorial_validator  # noqa: E402

POLICY = json.loads(
    (ROOT / "automation" / "config" / "editorial.json").read_text(encoding="utf-8")
)


def candidate(
    identifier: str,
    *,
    publisher: str,
    organization: str | None = None,
    recommendation: str = "consider",
    verified: bool = True,
) -> dict:
    return {
        "id": identifier,
        "organization": organization or identifier,
        "recommendation": recommendation,
        "verification_status": "verified" if verified else "unconfirmed",
        "freshness_status": "new_event",
        "category": "models",
        "legal_scale": "not_applicable",
        "significance_score": 3,
        "curiosity_eligible": False,
        "primary_source": {
            "publisher": publisher,
            "url": f"https://example.com/{identifier}",
        },
    }


def validate_stub(editorial: dict, research: dict, *args, **kwargs):
    del args, kwargs
    candidate_map = {
        item["id"]: item for item in research["candidates"] if isinstance(item, dict)
    }
    selected = [
        candidate_map[item]
        for item in editorial["selected_candidate_ids"]
        if item in candidate_map
    ]
    errors = validate_diversity_overrides(
        selected,
        editorial["diversity_overrides"],
        POLICY,
    )
    return errors, [], []


def run_wrapped(editorial: dict, research: dict):
    wrapped = wrap_editorial_validator(validate_stub, lambda value: value)
    return wrapped(editorial, research, None, None, None, POLICY, 7, 12)


class ShortPoolPublisherOverrideRuntimeTests(unittest.TestCase):
    def test_true_short_pool_synthesizes_only_missing_publisher_override(self) -> None:
        research = {
            "candidates": [
                candidate("a", publisher="TechCrunch"),
                candidate("b", publisher="TechCrunch"),
                candidate("c", publisher="TechCrunch"),
                candidate("d", publisher="Official"),
                candidate("e", publisher="Other"),
                candidate("x", publisher="Axios", recommendation="exclude", verified=False),
            ]
        }
        editorial = {
            "selected_candidate_ids": ["a", "b", "c", "d"],
            "diversity_overrides": [],
            "digest": {"editorial_notes": []},
        }

        errors, warnings, _stories = run_wrapped(editorial, research)

        self.assertEqual(errors, [])
        self.assertEqual(len(editorial["diversity_overrides"]), 1)
        override = editorial["diversity_overrides"][0]
        self.assertEqual(override["type"], "publisher")
        self.assertEqual(override["value"], "TechCrunch")
        self.assertIn("5 достойных кандидатов", override["reason"])
        self.assertEqual(editorial["digest"]["editorial_notes"][0]["type"], "diversity_override")
        self.assertTrue(any("publisher diversity override" in item for item in warnings))

    def test_normal_eligible_pool_keeps_existing_fail_closed_publisher_rule(self) -> None:
        research = {
            "candidates": [
                candidate("a", publisher="TechCrunch"),
                candidate("b", publisher="TechCrunch"),
                candidate("c", publisher="TechCrunch"),
                candidate("d", publisher="D"),
                candidate("e", publisher="E"),
                candidate("f", publisher="F"),
                candidate("g", publisher="G"),
            ]
        }
        editorial = {
            "selected_candidate_ids": ["a", "b", "c"],
            "diversity_overrides": [],
            "digest": {"editorial_notes": []},
        }

        errors, warnings, _stories = run_wrapped(editorial, research)

        self.assertTrue(any("techcrunch" in item.casefold() for item in errors))
        self.assertEqual(editorial["diversity_overrides"], [])
        self.assertFalse(any("publisher diversity override" in item for item in warnings))

    def test_short_pool_does_not_relax_organization_override(self) -> None:
        research = {
            "candidates": [
                candidate("a", publisher="A", organization="SameOrg"),
                candidate("b", publisher="B", organization="SameOrg"),
                candidate("c", publisher="C", organization="SameOrg"),
            ]
        }
        editorial = {
            "selected_candidate_ids": ["a", "b", "c"],
            "diversity_overrides": [],
            "digest": {"editorial_notes": []},
        }

        errors, _warnings, _stories = run_wrapped(editorial, research)

        self.assertTrue(any("sameorg" in item.casefold() for item in errors))
        self.assertEqual(editorial["diversity_overrides"], [])

    def test_existing_publisher_override_is_not_duplicated(self) -> None:
        research = {
            "candidates": [
                candidate("a", publisher="TechCrunch"),
                candidate("b", publisher="TechCrunch"),
                candidate("c", publisher="TechCrunch"),
            ]
        }
        manual = {
            "type": "publisher",
            "value": "TechCrunch",
            "reason": "Три независимых подтверждённых сюжета сохраняются в коротком пуле.",
        }
        editorial = {
            "selected_candidate_ids": ["a", "b", "c"],
            "diversity_overrides": [copy.deepcopy(manual)],
            "digest": {"editorial_notes": []},
        }

        errors, _warnings, _stories = run_wrapped(editorial, research)

        self.assertEqual(errors, [])
        self.assertEqual(editorial["diversity_overrides"], [manual])
        self.assertEqual(editorial["digest"]["editorial_notes"], [])


if __name__ == "__main__":
    unittest.main()
