from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "automation" / "scripts" / "validate_editorial_contract.py"
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_editorial_contract",
        VALIDATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load validate_editorial_contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EditorialContractSyncTests(unittest.TestCase):
    def test_editorial_contract_matches_repository(self) -> None:
        validator = load_validator()
        self.assertEqual(validator.validate(), [])

    def test_main_ci_runs_editorial_contract_validator(self) -> None:
        ci_text = CI_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "python automation/scripts/validate_editorial_contract.py",
            ci_text,
        )


if __name__ == "__main__":
    unittest.main()
