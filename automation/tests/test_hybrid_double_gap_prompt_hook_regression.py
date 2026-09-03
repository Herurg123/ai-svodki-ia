from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import hybrid_search_completeness as hybrid


class HybridDoubleGapPromptHookRegressionTests(unittest.TestCase):
    def test_public_wrapper_initializes_v2_prompt_hook_before_v3_delegation(self) -> None:
        base = hybrid.legacy._base
        had_original = hasattr(base, "build_prompt_original")
        saved_original = getattr(base, "build_prompt_original", None)
        saved_build_prompt = base.build_prompt
        sentinel_calls: list[dict] = []

        def sentinel_prompt(**kwargs):
            sentinel_calls.append(dict(kwargs))
            return "BASE HYBRID PROMPT"

        try:
            if had_original:
                delattr(base, "build_prompt_original")
            base.build_prompt = sentinel_prompt

            # This is the clean-process state that failed in production run
            # 33702310841 when the exceptional Asia+Russia v3 path called
            # v2.build_prompt directly before any normal v2 path had created the
            # compatibility hook.
            self.assertFalse(hasattr(base, "build_prompt_original"))
            hybrid._sync_compatibility_hooks()
            self.assertIs(base.build_prompt_original, sentinel_prompt)

            prompt = hybrid._v2.build_prompt(
                publication_date="2026-09-03",
                search_window={
                    "start_at": "2026-09-02T04:01:28+03:00",
                    "end_at": "2026-09-03T04:00:00+03:00",
                },
                direction_id="models_products_research",
                direction_label="Models / products / agents / research",
                direction_guidance="offline regression",
                existing_candidates=[],
                archive={"items": []},
            )
            self.assertIn("BASE HYBRID PROMPT", prompt)
            self.assertIn("Правило дедупликации жизненного цикла события", prompt)
            self.assertEqual(len(sentinel_calls), 1)
        finally:
            base.build_prompt = saved_build_prompt
            if had_original:
                base.build_prompt_original = saved_original
            elif hasattr(base, "build_prompt_original"):
                delattr(base, "build_prompt_original")

    def test_sync_is_zero_paid_and_does_not_change_search_ceilings(self) -> None:
        hybrid._sync_compatibility_hooks()
        self.assertEqual(hybrid.DEFAULT_MAXIMUM_SEARCH_CALLS, 4)
        self.assertEqual(hybrid.CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS, 5)
        self.assertEqual(hybrid.PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS, 24)
        self.assertEqual(hybrid.PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS, 25)


if __name__ == "__main__":
    unittest.main()
