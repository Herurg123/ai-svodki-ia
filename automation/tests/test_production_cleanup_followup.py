from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_previous_release_module():
    common_name = "production_daily_common"
    if common_name not in sys.modules:
        class CommonStub:
            @staticmethod
            def parse_rss(*args, **kwargs):
                raise RuntimeError("unused in unit test")

            @staticmethod
            def read_json(*args, **kwargs):
                raise RuntimeError("unused in unit test")

            @staticmethod
            def write_json(*args, **kwargs):
                raise RuntimeError("unused in unit test")

        sys.modules[common_name] = CommonStub()
    spec = importlib.util.spec_from_file_location(
        "production_cleanup_previous_release",
        SCRIPTS / "verify_previous_release.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous_release = load_previous_release_module()


class ProductionCleanupFollowupTests(unittest.TestCase):
    def test_image_only_recovery_skips_text_sdk(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "daily-production.yml"
        ).read_text(encoding="utf-8")
        start = workflow.index("- name: Install pinned OpenAI SDK")
        end = workflow.index("- name: Validate API configuration")
        install_block = workflow[start:end]
        self.assertIn("openai_needed", install_block)
        self.assertIn("text_api_needed", install_block)
        self.assertNotIn("image_api_needed", install_block)
        self.assertIn("IMAGE_API_NEEDED", workflow)

    def test_coverage_note_describes_both_seventh_slot_roles(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "daily-production.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("для повтора незавершённого направления", workflow)
        self.assertIn("high-signal recall sentinel", workflow)

    def test_live_previous_release_failure_is_diagnostic_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            posts = Path(temporary)
            (posts / "2026-07-25").mkdir()
            (posts / "2026-07-25" / "index.html").write_text(
                "ok", encoding="utf-8"
            )
            (posts / "images").mkdir()
            (posts / "images" / "ai-svodka-2026-07-25.png").write_bytes(b"png")

            def opener(request, timeout):
                del request, timeout
                raise urllib.error.URLError("temporary outage")

            report = previous_release.verify(
                config={
                    "site_base_url": "https://rybalka.one/posts",
                    "verify_previous_release_on_live_site": True,
                },
                rss={
                    "latest_item": {
                        "date": "2026-07-25",
                        "link": "https://rybalka.one/posts/2026-07-25/",
                    }
                },
                posts_root=posts,
                publication_date="2026-07-27",
                opener=opener,
            )

            self.assertEqual(report["status"], "ok")
            self.assertTrue(report["repository"]["verified"])
            self.assertFalse(report["live"]["verified"])
            self.assertTrue(report["live"]["diagnostic_only"])
            self.assertTrue(report["live"]["warnings"])


if __name__ == "__main__":
    unittest.main()
