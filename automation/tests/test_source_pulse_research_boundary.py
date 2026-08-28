from __future__ import annotations

import importlib.util
import json
import sys
import unittest
import urllib.request
from pathlib import Path

AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = AUTOMATION_ROOT.parent
MODULE_PATH = AUTOMATION_ROOT / "scripts" / "source_pulse.py"
spec = importlib.util.spec_from_file_location("source_pulse_boundary", MODULE_PATH)
sp = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = sp
spec.loader.exec_module(sp)


class SourcePulseResearchBoundaryTests(unittest.TestCase):
    def test_registry_is_shadow_only_and_has_no_candidate_influence(self):
        config_path = AUTOMATION_ROOT / "config" / "source-pulse-v1.json"
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["mode"], "production_shadow")
        self.assertTrue(payload["production_integration"])
        self.assertFalse(payload["candidate_influence"])
        self.assertFalse(payload["repoll_on_recovery"])
        registry = sp.load_registry(config_path)
        self.assertEqual(len(registry), 13)
        self.assertIn("tass_ai", {row.id for row in registry})

        workflow = REPOSITORY_ROOT / ".github" / "workflows" / "daily-production.yml"
        preview = AUTOMATION_ROOT / "scripts" / "run_digest_preview.py"
        hybrid = AUTOMATION_ROOT / "scripts" / "hybrid_search_completeness.py"
        self.assertNotIn("source_pulse", workflow.read_text(encoding="utf-8").casefold())
        self.assertNotIn("source_pulse", preview.read_text(encoding="utf-8").casefold())
        hybrid_text = hybrid.read_text(encoding="utf-8")
        self.assertIn("source_pulse_shadow", hybrid_text)
        self.assertIn("run_source_pulse_shadow", hybrid_text)

    def test_redirect_to_unlisted_host_is_rejected_before_follow(self):
        handler = sp.SafeRedirect(("good.example",))
        request = urllib.request.Request("https://good.example/start")
        with self.assertRaises(sp.SourcePulseError):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://evil.example/private",
            )


if __name__ == "__main__":
    unittest.main()
