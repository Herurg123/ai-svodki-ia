from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cleanup_public_posts import (  # noqa: E402
    PublicCleanupError,
    dated_images,
)
from repository_hygiene_github import (  # noqa: E402
    ApiError,
    GitHub,
)


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._raw


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://api.github.test/request",
        code,
        "temporary failure",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"temporary failure"}'),
    )


class PublicCleanupResilienceTests(unittest.TestCase):
    def test_missing_retired_legacy_image_directory_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            (posts / "images").mkdir(parents=True)
            (posts / "dzen-test").mkdir()
            canonical = posts / "images" / "ai-svodka-2026-08-18.png"
            canonical.write_bytes(b"image")

            self.assertEqual(dated_images(posts), {canonical})

    def test_primary_image_directory_remains_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            (posts / "dzen-test").mkdir(parents=True)

            with self.assertRaisesRegex(
                PublicCleanupError,
                "Post images directory must be a regular directory",
            ):
                dated_images(posts)


class RepositoryHygieneRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = GitHub(
            "Herurg123/ai-svodki-ia",
            "token",
            "https://api.github.test",
        )

    @patch("repository_hygiene_github.time.sleep")
    @patch("repository_hygiene_github.urllib.request.urlopen")
    def test_get_retries_transient_500_then_succeeds(self, urlopen, sleep) -> None:
        urlopen.side_effect = [
            http_error(500),
            FakeResponse(200, {"ok": True}),
        ]

        status, payload = self.api.request("GET", "/repos/example")

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1.0)

    @patch("repository_hygiene_github.time.sleep")
    @patch("repository_hygiene_github.urllib.request.urlopen")
    def test_get_stops_after_three_transient_failures(self, urlopen, sleep) -> None:
        urlopen.side_effect = [
            http_error(500),
            http_error(502),
            http_error(503),
        ]

        with self.assertRaisesRegex(ApiError, "HTTP 503"):
            self.api.request("GET", "/repos/example")

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])

    @patch("repository_hygiene_github.time.sleep")
    @patch("repository_hygiene_github.urllib.request.urlopen")
    def test_destructive_requests_are_never_retried(self, urlopen, sleep) -> None:
        urlopen.side_effect = http_error(500)

        with self.assertRaisesRegex(ApiError, "HTTP 500"):
            self.api.request("DELETE", "/repos/example/resource", (204,))

        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
