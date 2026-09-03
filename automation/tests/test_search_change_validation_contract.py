from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
MATRIX = ROOT / "automation" / "specs" / "search-change-validation-matrix.md"


def test_agents_requires_independent_search_change_matrix() -> None:
    text = AGENTS.read_text(encoding="utf-8")

    assert "automation/specs/search-change-validation-matrix.md" in text
    assert "current production baseline" in text
    assert "pairwise intersections" in text
    assert "new retrieval incident must enrich the canonical matrix" in text


def test_search_change_matrix_keeps_required_dimensions_and_combinations() -> None:
    text = MATRIX.read_text(encoding="utf-8")

    required_markers = [
        "0 релевантных результатов",
        "Dense pool выше candidate cap",
        "Один URL встречается у нескольких кандидатов",
        "Identity принадлежит невыбранному кандидату",
        "Одновременно Russia + China/Asia gaps",
        "Event точно вне окна, source свежий reprint",
        "Mandatory search timeout/error",
        "Caller передал oversized Hybrid limit",
        "Research-only saved artifact",
        "Порядок кандидатов/результатов provider изменён",
        "pairwise combinations",
        "unselected candidate identity + supporting-source contamination",
        "Green CI без такой независимой матрицы",
    ]
    for marker in required_markers:
        assert marker in text


def test_matrix_preserves_zero_paid_experiment_boundary() -> None:
    text = MATRIX.read_text(encoding="utf-8")

    assert "пользовательский production API budget" in text
    assert "не расходуется без отдельного разрешения" in text
    assert "Paid stages не повторяются ради regression" in text
    assert "Terra" in text
