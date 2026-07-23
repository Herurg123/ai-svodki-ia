from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from bootstrap_archive import ArticleParser, normalize_meta_marker


class BootstrapArchiveTests(unittest.TestCase):
    def test_meta_markers_are_removed_from_service_data(self) -> None:
        self.assertEqual(normalize_meta_marker("Meta*"), "Meta")
        self.assertEqual(normalize_meta_marker("Meta**"), "Meta")
        parser = ArticleParser()
        parser.feed("<h3>Meta** обновила продукт</h3><p>Meta* и Meta работают.</p>")
        self.assertEqual(parser.headings, [("h3", "Meta обновила продукт")])
        self.assertNotIn("Meta*", " ".join(parser.text_parts))


if __name__ == "__main__":
    unittest.main()
