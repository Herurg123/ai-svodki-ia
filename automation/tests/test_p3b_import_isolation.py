from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


class P3bImportIsolationTests(unittest.TestCase):
    def run_isolated(self, body: str) -> None:
        code = "import sys\n" + f"sys.path.insert(0, {str(SCRIPTS)!r})\n" + textwrap.dedent(body)
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"isolated import control failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )

    def test_standalone_v2_keeps_hardened_binder_after_legacy_first_and_sync(self) -> None:
        self.run_isolated(
            """
            import weak_source_exact_binding as legacy_binder
            import weak_source_exact_binding_v2 as hardened
            import ensure_story_coverage_p3b_v2 as v2

            assert v2.P3B_EXACT_BINDING_VERSION == 2
            assert v2.P3B_MODE == hardened.MODE
            assert v2.candidate_exact_binding is hardened.candidate_exact_binding
            assert v2.rejection_exact_terminal_binding is hardened.rejection_exact_terminal_binding
            assert v2._v1.P3B_EXACT_BINDING_VERSION == 1
            assert v2._v1.candidate_exact_binding is not hardened.candidate_exact_binding
            legacy_candidate = v2._v1.candidate_exact_binding
            legacy_negative = v2._v1.rejection_exact_terminal_binding

            v2._sync_p3b_public_hooks()

            assert v2.candidate_exact_binding is hardened.candidate_exact_binding
            assert v2.rejection_exact_terminal_binding is hardened.rejection_exact_terminal_binding
            assert v2._v1.P3B_EXACT_BINDING_VERSION == 1
            assert v2._v1.candidate_exact_binding is legacy_candidate
            assert v2._v1.rejection_exact_terminal_binding is legacy_negative
            assert legacy_binder.VERSION == 1
            """
        )

    def test_public_active_path_survives_historical_imports_afterward(self) -> None:
        self.run_isolated(
            """
            import ensure_story_coverage as public
            import ensure_story_coverage_p3b as historical_runtime
            import weak_source_exact_binding as historical_binder
            import ensure_story_coverage_p3b_v2 as direct_v2
            import weak_source_exact_binding_v2 as hardened

            public._sync_to_impl()
            assert public._impl._v2.candidate_exact_binding is hardened.candidate_exact_binding
            assert direct_v2.candidate_exact_binding is hardened.candidate_exact_binding
            assert historical_binder.VERSION == 1
            assert historical_runtime.P3B_EXACT_BINDING_VERSION == 1

            signal = {
                "signal_id": "import-order-control",
                "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
                "organization": "DeepSeek",
                "product_version_anchors": ["V4 Pro", "V4.1 Flash"],
                "lifecycle_action_anchors": ["replace"],
                "source_provenance": {"url": "https://weak.example/deepseek"},
            }
            candidate = {
                "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
                "organization": "DeepSeek",
                "event_type": "release",
                "recommendation": "include",
                "verification_status": "verified",
                "freshness_status": "new_event",
                "primary_source": {"url": "https://www.deepseek.com/en/news/v4-1-flash/"},
            }
            assert public.candidate_exact_binding(
                candidate,
                signal,
                authoritative_domains=("deepseek.com",),
            ) == (False, "authoritative_page_identity_unverified")
            assert public.rejection_exact_terminal_binding(
                {}, signal, authoritative_domains=("deepseek.com",)
            ) == (False, "terminal_negative_requires_independent_proof")
            """
        )

    def test_public_active_path_survives_direct_v2_import_before_wrapper(self) -> None:
        self.run_isolated(
            """
            import ensure_story_coverage_p3b_v2 as direct_v2
            direct_v2._sync_p3b_public_hooks()
            import ensure_story_coverage as public
            import weak_source_exact_binding_v2 as hardened

            public._sync_to_impl()
            assert direct_v2.candidate_exact_binding is hardened.candidate_exact_binding
            assert public._impl._v2.candidate_exact_binding is hardened.candidate_exact_binding
            assert public._impl._v2._v1.P3B_EXACT_BINDING_VERSION == 1
            assert public.P3B_EXACT_BINDING_VERSION == 2
            """
        )


if __name__ == "__main__":
    unittest.main()
