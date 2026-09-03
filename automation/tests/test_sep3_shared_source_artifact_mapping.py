from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_digest_artifact as validator

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "artifact-shared-source-2026-09-03.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def empty_report() -> dict:
    return {"errors": [], "warnings": []}


def codes(report: dict) -> list[str]:
    return [row["code"] for row in report["errors"]]


def test_sep3_shared_source_replay_maps_by_story_identity_not_global_url_uniqueness() -> None:
    fixture = load_fixture()
    candidates = fixture["candidates"]["candidates"]
    shared = validator.recursive_urls(candidates[0]) & validator.recursive_urls(candidates[1])
    assert fixture["shared_url"] in shared

    report = empty_report()
    validator.validate_story_mapping(
        fixture["article_html"],
        fixture["candidates"],
        fixture["selection"],
        fixture["stories"],
        report,
    )

    assert report["errors"] == []


def test_article_link_must_match_final_story_sources_even_when_candidate_has_it() -> None:
    fixture = load_fixture()
    bad = copy.deepcopy(fixture)
    huggingnews = bad["candidates"]["candidates"][1]["primary_source"]["url"]
    bad["article_html"] = bad["article_html"].replace(
        fixture["shared_url"], huggingnews
    )

    report = empty_report()
    validator.validate_story_mapping(
        bad["article_html"],
        bad["candidates"],
        bad["selection"],
        bad["stories"],
        report,
    )

    assert codes(report) == ["article_story_source_mismatch"]


def test_story_source_must_belong_to_expected_candidate() -> None:
    fixture = load_fixture()
    bad = copy.deepcopy(fixture)
    foreign = "https://example.com/not-present-in-meta-candidate"
    bad["stories"][1]["sources"][0]["url"] = foreign
    bad["article_html"] = bad["article_html"].replace(fixture["shared_url"], foreign)

    report = empty_report()
    validator.validate_story_mapping(
        bad["article_html"],
        bad["candidates"],
        bad["selection"],
        bad["stories"],
        report,
    )

    assert codes(report) == ["story_source_not_candidate"]


def test_shared_url_cannot_hide_swapped_html_story_order() -> None:
    fixture = load_fixture()
    bad = copy.deepcopy(fixture)
    first = bad["stories"][0]["headline"]
    second = bad["stories"][1]["headline"]
    html = bad["article_html"]
    html = html.replace(first, "__FIRST__", 1)
    html = html.replace(second, first, 1)
    bad["article_html"] = html.replace("__FIRST__", second, 1)

    report = empty_report()
    validator.validate_story_mapping(
        bad["article_html"],
        bad["candidates"],
        bad["selection"],
        bad["stories"],
        report,
    )

    assert codes(report).count("story_headline_order") == 2


def test_stories_candidate_id_order_remains_fail_closed() -> None:
    fixture = load_fixture()
    bad = copy.deepcopy(fixture)
    bad["stories"] = list(reversed(bad["stories"]))

    report = empty_report()
    validator.validate_story_mapping(
        bad["article_html"],
        bad["candidates"],
        bad["selection"],
        bad["stories"],
        report,
    )

    assert "story_order" in codes(report)
    assert "story_headline_order" in codes(report)
