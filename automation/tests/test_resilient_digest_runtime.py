from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy_runtime import (  # noqa: E402
    normalize_editorial_sources,
    wrap_editorial_validator,
)
from run_digest_preview import (  # noqa: E402
    normalize_completed_empty_research,
    provisional_artifact_is_reusable,
)


def simple_normalize_url(value: str) -> str:
    return value.rstrip("/")


class EmptyResearchRecoveryTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def make_artifact(
        self,
        root: Path,
        *,
        response_status: str = "completed",
        web_search_calls: int = 3,
        message: str = "Пул кандидатов пуст, не найдено ни одного события.",
    ) -> None:
        self.write_json(
            root / "candidates.json",
            {
                "status": "error",
                "error_message": message,
                "coverage": [{"area": "world", "status": "gap", "notes": "none"}],
                "search_window": {"start_at": "a", "end_at": "b"},
                "candidates": [],
            },
        )
        self.write_json(root / "research-output-raw.json", {"status": "error"})
        self.write_json(
            root / "run-info.json",
            {
                "status": "error",
                "warnings": [],
                "research": {
                    "status": "error",
                    "error": message,
                    "response": {
                        "response_status": response_status,
                        "web_search_calls": web_search_calls,
                    },
                },
                "error": message,
            },
        )

    def test_completed_empty_research_becomes_audit_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_artifact(root)

            self.assertTrue(normalize_completed_empty_research(root))
            self.assertTrue(provisional_artifact_is_reusable(root))

            candidates = json.loads((root / "candidates.json").read_text(encoding="utf-8"))
            run_info = json.loads((root / "run-info.json").read_text(encoding="utf-8"))
            self.assertEqual(candidates["status"], "ok")
            self.assertIsNone(candidates["error_message"])
            self.assertEqual(run_info["research"]["status"], "ok")
            self.assertTrue(run_info["warnings"])

    def test_transport_failure_is_not_reclassified_as_empty_news_day(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_artifact(root, response_status="failed")

            self.assertFalse(normalize_completed_empty_research(root))
            self.assertFalse(provisional_artifact_is_reusable(root))

    def test_completed_response_without_search_is_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_artifact(root, web_search_calls=0)

            self.assertFalse(normalize_completed_empty_research(root))


class EditorialSourceNormalizationTests(unittest.TestCase):
    def research(self) -> dict:
        return {
            "candidates": [
                {
                    "id": "cand-001",
                    "primary_source": {
                        "title": "Official announcement",
                        "publisher": "Hark",
                        "url": "https://hark.com/story/",
                    },
                    "supporting_sources": [
                        {
                            "title": "Independent report",
                            "publisher": "TechCrunch",
                            "url": "https://techcrunch.com/report/",
                        }
                    ],
                }
            ]
        }

    def test_known_url_gets_exact_research_metadata(self) -> None:
        editorial = {
            "digest": {
                "article_html": (
                    '<h3>Story</h3><p><a href="https://techcrunch.com/report">'
                    "Source</a></p>"
                ),
                "sources": [
                    {
                        "title": "Changed title",
                        "publisher": "Tech Crunch",
                        "url": "https://techcrunch.com/report",
                    }
                ],
            }
        }
        changes = normalize_editorial_sources(
            editorial,
            self.research(),
            simple_normalize_url,
        )
        self.assertEqual(len(changes), 2)
        self.assertEqual(
            editorial["digest"]["sources"][0],
            self.research()["candidates"][0]["supporting_sources"][0],
        )
        self.assertIn(
            'href="https://techcrunch.com/report/"',
            editorial["digest"]["article_html"],
        )

    def test_unknown_url_is_left_for_original_validator(self) -> None:
        source = {
            "title": "Unknown",
            "publisher": "Unknown",
            "url": "https://example.com/new",
        }
        editorial = {"digest": {"sources": [dict(source)]}}
        changes = normalize_editorial_sources(
            editorial,
            self.research(),
            simple_normalize_url,
        )
        self.assertEqual(changes, [])
        self.assertEqual(editorial["digest"]["sources"][0], source)

    def test_wrapper_normalizes_before_original_validation(self) -> None:
        observed: list[dict] = []

        def original(editorial: dict, research: dict, *args, **kwargs):
            observed.append(dict(editorial["digest"]["sources"][0]))
            return [], []

        wrapped = wrap_editorial_validator(original, simple_normalize_url)
        editorial = {
            "digest": {
                "sources": [
                    {
                        "title": "Independent report",
                        "publisher": "TechCrunch",
                        "url": "https://techcrunch.com/report",
                    }
                ]
            }
        }
        self.assertEqual(wrapped(editorial, self.research()), ([], []))
        self.assertEqual(
            observed[0]["url"],
            "https://techcrunch.com/report/",
        )


if __name__ == "__main__":
    unittest.main()
