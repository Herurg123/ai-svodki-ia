from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
TESTS = ROOT / "automation" / "tests"
sys.path[:0] = [str(SCRIPTS), str(TESTS)]

import test_p3b_astra_regressions as controls
import test_p3b_recovery_ownership_priority as priority

coverage = controls.coverage
DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
SIGNAL = controls.SIGNAL


class P3bPriorityDiagnosticTmp(unittest.TestCase):
    def test_priority_predicate_survives_compat_sync(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            helper = priority.P3bRecoveryOwnershipPriorityTests()
            plan = helper._six_mandatory_plan(state)
            helper._reservation(state, plan)
            required = [helper._required_signal()]
            active_v2 = coverage._impl._v2
            original_v2_sync = active_v2._sync_p3b_public_hooks

            def fake_p3a_execute(*args, **kwargs):
                return copy.deepcopy(plan)

            def sync_then_install_required_probe() -> None:
                original_v2_sync()
                active_v2._v1._P3A_EXECUTE_AUDIT_PLAN = fake_p3a_execute

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
                mock.patch.object(active_v2, "_sync_p3b_public_hooks", side_effect=sync_then_install_required_probe),
            ):
                coverage._sync_to_impl()
                impl = coverage._impl
                impl._sync_p3b_public_hooks()
                journal, invalid = impl._v4._load_optional_journal(DATE)
                required_before = list(impl._v2._pre._required_signals(DATE))
                rows = impl._p3b_signals(DATE)
                selected = impl.select_p3b_signal(rows)
                exact_match = impl._v5._journal_matches_current_p3b_intent_v5(
                    publication_date=DATE,
                    journal=journal,
                    model=MODEL,
                    search_window=copy.deepcopy(WINDOW),
                    archive={"items": []},
                    signal=selected,
                ) if isinstance(journal, dict) else False
                legacy_match = bool(
                    required_before
                    and isinstance(journal, dict)
                    and impl._journal_matches_current_legacy_intent_v6(
                        journal=journal,
                        model=MODEL,
                        search_window=copy.deepcopy(WINDOW),
                        archive={"items": []},
                        required_signals=required_before,
                    )
                )
                predicate = bool(
                    required_before
                    and isinstance(journal, dict)
                    and not legacy_match
                    and exact_match
                )
                print(
                    "P3B_PRIORITY_DIAG",
                    {
                        "invalid": invalid,
                        "required_count": len(required_before),
                        "rows_count": len(rows),
                        "selected_signal_id": (selected or {}).get("signal_id"),
                        "journal_owner": (journal or {}).get("owner") if isinstance(journal, dict) else None,
                        "journal_state": (journal or {}).get("state") if isinstance(journal, dict) else None,
                        "exact_match": exact_match,
                        "legacy_match": legacy_match,
                        "predicate": predicate,
                    },
                )
                self.assertTrue(required_before)
                self.assertEqual(len(rows), 1)
                self.assertIsNotNone(selected)
                self.assertTrue(exact_match)
                self.assertFalse(legacy_match)
                self.assertTrue(predicate)


if __name__ == "__main__":
    unittest.main()
