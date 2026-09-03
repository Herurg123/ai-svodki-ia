from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_digest_artifact as validator

FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "recall"
    / "artifact-shared-source-2026-09-03.json"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def empty_report() -> dict:
    return {"errors": [], "warnings": []}


def codes(report: dict) -> list[str]:
    return [row["code"] for row in report["errors"]]


def validate(fixture: dict) -> dict:
    report = empty_report()
    validator.validate_story_mapping(
        fixture["article_html"],
        fixture["candidates"],
        fixture["selection"],
        fixture["stories"],
        report,
    )
    return report


class CrossCandidateIdentityProvenanceTests(unittest.TestCase):
    def test_sep3_real_shared_source_fixture_still_passes(self) -> None:
        fixture = load_fixture()
        self.assertIn(
            fixture["shared_url"],
            validator.candidate_identity_urls(
                fixture["candidates"]["candidates"][1]
            ),
        )
        self.assertEqual(validate(fixture)["errors"], [])

    def test_foreign_identity_cannot_hide_inside_expected_supporting_sources(
        self,
    ) -> None:
        fixture = load_fixture()
        bad = copy.deepcopy(fixture)
        google = bad["candidates"]["candidates"][0]
        shared = bad["shared_url"]

        google_primary = google["primary_source"]["url"]
        bad["stories"][0]["sources"] = [
            copy.deepcopy(google["supporting_sources"][0])
        ]
        bad["article_html"] = bad["article_html"].replace(
            google_primary,
            shared,
            1,
        )

        report = validate(bad)

        self.assertEqual(codes(report), ["story_source_identity_conflict"])

    def test_expected_candidate_may_use_identity_shared_as_someone_elses_support(
        self,
    ) -> None:
        fixture = load_fixture()
        meta = fixture["candidates"]["candidates"][1]
        shared = fixture["shared_url"]

        self.assertEqual(meta["event_origin_url"], shared)
        self.assertEqual(validate(fixture)["errors"], [])

    def test_unique_supporting_source_remains_valid_final_evidence(self) -> None:
        fixture = load_fixture()
        changed = copy.deepcopy(fixture)
        google = changed["candidates"]["candidates"][0]
        google_primary = google["primary_source"]["url"]
        unique = {
            "title": "Independent corroboration",
            "publisher": "Example",
            "url": "https://example.com/google-independent-corroboration",
        }
        google["supporting_sources"].append(unique)
        changed["stories"][0]["sources"] = [copy.deepcopy(unique)]
        changed["article_html"] = changed["article_html"].replace(
            google_primary,
            unique["url"],
            1,
        )

        self.assertEqual(validate(changed)["errors"], [])

    def test_shared_identity_owned_by_expected_candidate_is_not_rejected(
        self,
    ) -> None:
        fixture = load_fixture()
        changed = copy.deepcopy(fixture)
        google = changed["candidates"]["candidates"][0]
        shared = changed["shared_url"]
        google_primary = google["primary_source"]["url"]

        google["event_origin_url"] = shared
        changed["stories"][0]["sources"] = [
            copy.deepcopy(google["supporting_sources"][0])
        ]
        changed["article_html"] = changed["article_html"].replace(
            google_primary,
            shared,
            1,
        )

        self.assertEqual(validate(changed)["errors"], [])

    def test_unselected_candidate_identity_still_blocks_contamination(self) -> None:
        fixture = load_fixture()
        bad = copy.deepcopy(fixture)
        google = bad["candidates"]["candidates"][0]
        google_primary = google["primary_source"]["url"]
        foreign_url = "https://example.com/unselected-candidate-identity"
        foreign_source = {
            "title": "Unselected identity",
            "publisher": "Example",
            "url": foreign_url,
        }
        google["supporting_sources"].append(copy.deepcopy(foreign_source))
        bad["candidates"]["candidates"].append(
            {
                "id": "cand-999",
                "title": "Unselected candidate",
                "primary_source": copy.deepcopy(foreign_source),
                "supporting_sources": [],
            }
        )
        bad["stories"][0]["sources"] = [copy.deepcopy(foreign_source)]
        bad["article_html"] = bad["article_html"].replace(
            google_primary,
            foreign_url,
            1,
        )

        report = validate(bad)

        self.assertEqual(codes(report), ["story_source_identity_conflict"])

    def test_pairwise_identity_contamination_matrix_fails_closed(self) -> None:
        size = 7
        candidates = []
        for index in range(size):
            cid = f"cand-{index + 1:03d}"
            url = f"https://example.com/identity/{cid}"
            candidates.append(
                {
                    "id": cid,
                    "title": f"Story {cid}",
                    "primary_source": {
                        "title": f"Primary {cid}",
                        "publisher": "Example",
                        "url": url,
                    },
                    "supporting_sources": [],
                }
            )

        checked = 0
        for expected_index in range(size):
            for owner_index in range(size):
                if expected_index == owner_index:
                    continue

                contaminated = copy.deepcopy(candidates)
                expected_copy = contaminated[expected_index]
                owner_source = copy.deepcopy(
                    contaminated[owner_index]["primary_source"]
                )
                expected_copy["supporting_sources"].append(owner_source)

                expected_id = expected_copy["id"]
                headline = expected_copy["title"]
                payload = {
                    "candidates": {"candidates": contaminated},
                    "selection": {"selected_candidate_ids": [expected_id]},
                    "stories": [
                        {
                            "candidate_id": expected_id,
                            "headline": headline,
                            "sources": [owner_source],
                        }
                    ],
                    "article_html": (
                        f'<h3>{headline}</h3><p>Text '
                        f'<a href="{owner_source["url"]}">source</a>.</p>'
                    ),
                }
                report = empty_report()
                validator.validate_story_mapping(
                    payload["article_html"],
                    payload["candidates"],
                    payload["selection"],
                    payload["stories"],
                    report,
                )

                self.assertEqual(
                    codes(report),
                    ["story_source_identity_conflict"],
                )
                checked += 1

        self.assertEqual(checked, size * (size - 1))


if __name__ == "__main__":
    unittest.main()
