from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "automation" / "prompts" / "primary_recall_pass.md"
PRIMARY = ROOT / "automation" / "scripts" / "primary_recall_search_v2.py"
HYBRID = ROOT / "automation" / "scripts" / "hybrid_search_completeness_v1.py"


def test_major_agencies_query_covers_business_and_earnings_without_new_slot():
    text = PROMPT.read_text(encoding="utf-8")
    assert (
        "latest AI chips infrastructure financing earnings business deals policy security"
        in text
    )
    assert "ровно `latest AI chips data centers investments deals policy security`" not in text

    primary = PRIMARY.read_text(encoding="utf-8")
    assert "DEFAULT_MAXIMUM_SEARCH_CALLS = 12" in primary
    assert '"id": "major_agencies"' in primary


def test_second_asia_pass_adds_business_semantics_but_preserves_two_passes():
    text = PROMPT.read_text(encoding="utf-8")
    assert (
        "latest China Asia AI business earnings revenue strategy cloud partnerships deployments"
        in text
    )
    for term in ("business", "earnings", "revenue", "strategy", "partnerships", "deployments"):
        assert term in text

    primary = PRIMARY.read_text(encoding="utf-8")
    assert '"id": "china_asia_models"' in primary
    assert '"id": "china_asia_integrations"' in primary
    assert primary.index('"id": "china_asia_models"') < primary.index(
        '"id": "china_asia_integrations"'
    )


def test_russia_and_hybrid_adaptive_capacity_are_unchanged():
    primary = PRIMARY.read_text(encoding="utf-8")
    hybrid = HYBRID.read_text(encoding="utf-8")
    assert '"id": "russia"' in primary
    assert "DEFAULT_MAXIMUM_SEARCH_CALLS = 12" in primary
    assert "MAXIMUM_SEARCH_CALLS = 4" in hybrid
    assert "ADAPTIVE_SEARCH_CALLS = 1" in hybrid
