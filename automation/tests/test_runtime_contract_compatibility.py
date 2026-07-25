from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeContractCompatibilityTests(unittest.TestCase):
    def test_digest_wrapper_keeps_historical_agent_helper(self) -> None:
        wrapper = load_module(
            "runtime_contract_digest_wrapper",
            SCRIPTS / "run_digest_preview.py",
        )
        self.assertFalse(
            wrapper.actual_prohibited_agent_form("Meta AI агентные функции")
        )
        self.assertTrue(
            wrapper.actual_prohibited_agent_form("Новый AI-агент работает")
        )

    def test_all_policy_consumers_use_shared_runtime(self) -> None:
        for name in (
            "run_digest_preview.py",
            "run_build_site.py",
            "run_validate_site.py",
        ):
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            self.assertIn("editorial_policy_runtime", text)
            self.assertIn("patch_editorial_policy", text)


if __name__ == "__main__":
    unittest.main()
