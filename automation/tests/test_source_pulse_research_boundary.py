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
    def test_registry_is_research_only_and_not_wired_into_production(self):
        config_path = AUTOMATION_ROOT / "config" / "source-pulse-v1.json"
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["mode"], "research_only")
        self.assertFalse(payload["production_integration"])
        self.assertEqual(len(sp.load_registry(config_path)), 12)

        production_surfaces = [
            REPOSITORY_ROOT / ".github" / "workflows" / "daily-production.yml",
            AUTOMATION_ROOT / "scripts" / "run_digest_preview.py",
        ]
        for path in production_surfaces:
            text = path.read_text(encoding="utf-8").casefold()
            self.assertNotIn("source_pulse", text, str(path))
            self.assertNotIn("source-pulse-v1", text, str(path))

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
