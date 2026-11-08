from __future__ import annotations

import http.client
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))
from repository_hygiene_github import ApiError, GitHub


class IncompleteReadRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.api = GitHub("test/repo", "dummy", "https://api.github.invalid")

    def test_incomplete_read_get_retries_then_succeeds(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"ok": true}'
        with patch("urllib.request.urlopen", side_effect=[
            http.client.IncompleteRead(b"", 40), Response(),
        ]) as open_mock, patch("time.sleep") as sleep_mock:
            self.assertEqual(self.api.request("GET", "/foo"), (200, {"ok": True}))
        self.assertEqual(open_mock.call_count, 2)
        sleep_mock.assert_called_once_with(1.0)

    def test_incomplete_read_does_not_retry_destructive_operation(self):
        with patch("urllib.request.urlopen",
                   side_effect=http.client.IncompleteRead(b"", 40)) as open_mock, patch("time.sleep") as sleep_mock:
            with self.assertRaises(ApiError):
                self.api.request("DELETE", "/foo", (204,))
        open_mock.assert_called_once()
        sleep_mock.assert_not_called()

    def test_incomplete_read_exhausts_get_retries(self):
        with patch("urllib.request.urlopen",
                   side_effect=http.client.IncompleteRead(b"", 40)) as open_mock, patch("time.sleep") as sleep_mock:
            with self.assertRaises(ApiError):
                self.api.request("GET", "/foo")
        self.assertEqual(open_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
