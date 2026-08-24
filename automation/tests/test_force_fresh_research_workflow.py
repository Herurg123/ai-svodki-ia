from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"


class ForceFreshResearchWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_input_is_manual_boolean_default_false(self):
        self.assertRegex(
            self.text,
            r"force_fresh_research:\n"
            r"\s+description: .*\n"
            r"\s+required: true\n"
            r"\s+default: false\n"
            r"\s+type: boolean",
        )

    def test_force_fresh_is_scoped_to_workflow_dispatch(self):
        self.assertIn('EVENT_NAME: ${{ github.event_name }}', self.text)
        self.assertIn(
            'FORCE_FRESH_RESEARCH: ${{ inputs.force_fresh_research || \'false\' }}',
            self.text,
        )
        self.assertIn(
            'if [[ "${EVENT_NAME}" == "workflow_dispatch" && "${FORCE_FRESH_RESEARCH}" == "true" ]]; then',
            self.text,
        )
        self.assertNotIn('if [[ "${EVENT_NAME}" == "schedule" && "${FORCE_FRESH_RESEARCH}" == "true"', self.text)

    def test_force_fresh_and_manual_recovery_id_are_mutually_exclusive(self):
        self.assertIn(
            '"${FORCE_FRESH_RESEARCH}" == "true" && -n "${MANUAL_RECOVERY_RUN_ID}"',
            self.text,
        )
        self.assertIn(
            "force_fresh_research=true conflicts with recovery_run_id",
            self.text,
        )

    def test_force_fresh_disables_automatic_recovery_selection(self):
        forced = self.text.index('Manual fresh research requested; automatic recovery is disabled for this run.')
        automatic = self.text.index('source="automatic"', forced)
        self.assertLess(forced, automatic)
        forced_block = self.text[self.text.rfind('if [[ "${EVENT_NAME}"', 0, forced):automatic]
        self.assertIn('run_id=""', forced_block)
        self.assertIn('source="none"', forced_block)
        self.assertIn('elif [[ -z "${run_id}" ]]; then', forced_block)

    def test_terminal_reuse_still_requires_selected_artifact(self):
        self.assertIn(
            "- name: Reuse completed editorial stop without paid APIs\n"
            "        id: terminal_reuse\n"
            "        if: steps.recovery_source.outputs.run_id != ''",
            self.text,
        )

    def test_fresh_research_path_and_publish_dry_run_contract_are_unchanged(self):
        self.assertIn(
            "- name: Run full research and editorial\n"
            "        if: steps.recovery.outputs.reused != 'true' && steps.terminal_reuse.outputs.stop != 'true'",
            self.text,
        )
        self.assertIn('MANUAL_PUBLISH: ${{ inputs.publish || \'false\' }}', self.text)
        self.assertIn('if [[ "${PUBLISH}" != "true" ]]; then', self.text)
        self.assertIn('args+=(--dry-run)', self.text)


if __name__ == "__main__":
    unittest.main()
