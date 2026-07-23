from __future__ import annotations

import copy
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

from generate_digest_preview import normalize_candidate_sources  # noqa: E402


class ResearchSourceNormalizationTests(unittest.TestCase):
    def test_duplicate_urls_are_normalized_without_dropping_candidates(self) -> None:
        axios_primary = {
            "title": "Nvidia CEO discusses Kimi",
            "publisher": "Axios",
            "url": "https://www.axios.com/2026/07/23/nvidia-ceo-kimi-ai-fears-trump-washington",
        }
        candidates = [
            {
                "id": "cand-001",
                "primary_source": copy.deepcopy(axios_primary),
                "supporting_sources": [
                    {
                        "title": "Same Axios link with tracking",
                        "publisher": "Axios",
                        "url": axios_primary["url"] + "?utm_source=test",
                    },
                    {
                        "title": "Independent source",
                        "publisher": "Reuters",
                        "url": "https://www.reuters.com/technology/example",
                    },
                ],
            },
            {
                "id": "cand-002",
                "primary_source": {
                    "title": "Official announcement",
                    "publisher": "Example",
                    "url": "https://example.com/announcement",
                },
                "supporting_sources": [
                    {
                        "title": "Different metadata for reused Axios link",
                        "publisher": "Axios Media",
                        "url": axios_primary["url"],
                    }
                ],
            },
        ]

        report = normalize_candidate_sources(candidates)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            [source["url"] for source in candidates[0]["supporting_sources"]],
            ["https://www.reuters.com/technology/example"],
        )
        self.assertEqual(candidates[1]["supporting_sources"], [axios_primary])
        self.assertEqual(len(report["removed_supporting_duplicates"]), 1)
        self.assertEqual(len(report["canonicalized_sources"]), 1)
        self.assertEqual(
            report["reused_urls"],
            [
                {
                    "url": axios_primary["url"],
                    "candidate_ids": ["cand-001", "cand-002"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
