from __future__ import annotations

import datetime as dt
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import repository_hygiene_video_rss_runs as video_hygiene  # noqa: E402

REPO = "Herurg123/ai-svodki-ia"


def run(
    run_id: int,
    created_at: str,
    *,
    conclusion: str | None = "success",
    status: str = "completed",
    updated_at: str | None = None,
    workflow_id: int = 10,
) -> dict:
    return {
        "id": run_id,
        "workflow_id": workflow_id,
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "updated_at": updated_at or created_at,
    }


class FakeApi:
    repository = REPO

    def __init__(self, runs: list[dict]) -> None:
        self.video_runs = list(runs)
        self.deleted: list[int] = []
        self.pages_seen: list[int] = []
        self.main_sha = "a" * 40
        self.active_production_runs: list[dict] = []

    def branch(self, name: str):
        if name == "main":
            return {"name": "main", "commit": {"sha": self.main_sha}}
        return None

    def workflows(self):
        return [
            {
                "id": 10,
                "name": "Video RSS enrichment",
                "path": video_hygiene.VIDEO_RSS_WORKFLOW_PATH,
                "state": "active",
            },
            {
                "id": 20,
                "name": "Daily production digest",
                "path": video_hygiene.DAILY_PRODUCTION_WORKFLOW_PATH,
                "state": "active",
            },
        ]

    def runs(self, status: str):
        return [item for item in self.active_production_runs if item.get("status") == status]

    def request(self, method: str, path: str, expected=(200,)):
        if method == "GET" and "/actions/workflows/10/runs?" in path:
            match = re.search(r"[?&]page=(\d+)", path)
            assert match
            page = int(match.group(1))
            self.pages_seen.append(page)
            start = (page - 1) * 100
            return 200, {"workflow_runs": self.video_runs[start : start + 100]}
        if method == "GET" and "/actions/runs/" in path:
            run_id = int(path.rsplit("/", 1)[1])
            current = next((item for item in self.video_runs if int(item["id"]) == run_id), None)
            return (200, current) if current is not None else (404, None)
        raise AssertionError((method, path, expected))

    def delete_run(self, run_id: int) -> None:
        self.deleted.append(run_id)
        self.video_runs = [item for item in self.video_runs if int(item["id"]) != run_id]


class VideoRssRunHygieneTests(unittest.TestCase):
    NOW = dt.datetime(2026, 8, 27, 6, 0, tzinfo=dt.timezone.utc)

    def test_pagination_reaches_beyond_first_hundred_runs(self) -> None:
        runs = [
            run(
                10_000 - index,
                (self.NOW - dt.timedelta(minutes=5 * index)).isoformat().replace("+00:00", "Z"),
            )
            for index in range(900)
        ]
        api = FakeApi(runs)

        fetched = video_hygiene.workflow_runs_all(api, 10)

        self.assertEqual(len(fetched), 900)
        self.assertEqual(api.pages_seen, list(range(1, 11)))

    def test_three_day_success_retention_and_latest_fourteen_floor(self) -> None:
        newest = [
            run(
                100 + index,
                (self.NOW - dt.timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
            )
            for index in range(14)
        ]
        edge_old = run(1, "2026-08-24T06:00:00Z")
        edge_new = run(2, "2026-08-24T06:00:01Z")

        classes = video_hygiene.classify_video_rss_runs(
            [*newest, edge_old, edge_new],
            self.NOW,
        )

        self.assertEqual(classes[1], ("safe_delete", "expired_video_rss_success"))
        self.assertEqual(classes[2], ("protected", "recent_video_rss_success"))

        ancient = [
            run(300 + index, f"2026-07-{10 + index:02d}T00:00:00Z")
            for index in range(15)
        ]
        ancient_classes = video_hygiene.classify_video_rss_runs(ancient, self.NOW)
        self.assertEqual(
            sum(reason == "video_rss_success_floor" for _, reason in ancient_classes.values()),
            14,
        )
        self.assertEqual(
            sum(classification == "safe_delete" for classification, _ in ancient_classes.values()),
            1,
        )

    def test_diagnostics_active_unknown_and_recent_rerun_are_protected(self) -> None:
        floor = [
            run(
                500 + index,
                (self.NOW - dt.timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
            )
            for index in range(14)
        ]
        cases = [
            run(3, "2026-08-13T06:00:00Z", conclusion="failure"),
            run(4, "2026-08-13T06:00:01Z", conclusion="cancelled"),
            run(5, "2026-07-01T00:00:00Z", conclusion=None, status="in_progress"),
            run(6, "2026-07-01T00:00:00Z", conclusion="skipped"),
            run(
                7,
                "2026-07-01T00:00:00Z",
                updated_at="2026-08-27T05:00:00Z",
            ),
        ]

        classes = video_hygiene.classify_video_rss_runs([*floor, *cases], self.NOW)

        self.assertEqual(classes[3], ("safe_delete", "expired_video_rss_diagnostic"))
        self.assertEqual(classes[4], ("protected", "recent_video_rss_diagnostic"))
        self.assertEqual(classes[5], ("protected", "video_rss_run_not_completed"))
        self.assertEqual(classes[6], ("review_only", "unhandled_video_rss_conclusion"))
        self.assertEqual(classes[7], ("protected", "recent_video_rss_success"))

    def test_apply_deletes_only_revalidated_safe_runs(self) -> None:
        ancient = [
            run(700 + index, f"2026-07-{10 + index:02d}T00:00:00Z")
            for index in range(15)
        ]
        api = FakeApi(ancient)
        plan = video_hygiene.build_plan(api, self.NOW)

        result = video_hygiene.apply_plan(api, plan)

        self.assertIsNone(result.get("skipped"))
        self.assertEqual(len(result["deleted"]), 1)
        self.assertEqual(len(api.deleted), 1)
        self.assertEqual(len(api.video_runs), 14)

    def test_apply_stops_when_video_rss_run_is_active(self) -> None:
        ancient = [
            run(800 + index, f"2026-07-{10 + index:02d}T00:00:00Z")
            for index in range(15)
        ]
        ancient.append(
            run(
                999,
                "2026-08-27T05:59:00Z",
                conclusion=None,
                status="in_progress",
            )
        )
        api = FakeApi(ancient)
        plan = video_hygiene.build_plan(api, self.NOW)

        result = video_hygiene.apply_plan(api, plan)

        self.assertEqual(result["skipped"], "active_video_rss_run")
        self.assertEqual(api.deleted, [])

    def test_daily_hygiene_workflow_owns_plan_and_apply(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "repository-hygiene.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("repository_hygiene_video_rss_runs.py", workflow)
        self.assertIn("video-rss-runs-plan.json", workflow)
        self.assertIn("video-rss-runs-actions.json", workflow)
        self.assertIn("--mode plan", workflow)
        self.assertIn("--mode apply", workflow)
        self.assertNotIn("MAIN_PUSH_DEPLOY_KEY", workflow)


if __name__ == "__main__":
    unittest.main()
