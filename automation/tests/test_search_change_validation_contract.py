from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
MATRIX = ROOT / "automation" / "specs" / "search-change-validation-matrix.md"


class SearchChangeValidationContractTests(unittest.TestCase):
    def test_agents_requires_independent_search_change_matrix(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")

        self.assertIn("automation/specs/search-change-validation-matrix.md", text)
        self.assertIn("current production baseline", text)
        self.assertIn("pairwise intersections", text)
        self.assertIn(
            "new retrieval incident must enrich the canonical matrix",
            text,
        )

    def test_search_change_matrix_keeps_required_dimensions_and_combinations(
        self,
    ) -> None:
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
            self.assertIn(marker, text)

    def test_matrix_preserves_zero_paid_experiment_boundary(self) -> None:
        text = MATRIX.read_text(encoding="utf-8")

        self.assertIn("пользовательский production API budget", text)
        self.assertIn("не расходуется без отдельного разрешения", text)
        self.assertIn("Paid stages не повторяются ради regression", text)
        self.assertIn("Terra", text)


if __name__ == "__main__":
    unittest.main()
