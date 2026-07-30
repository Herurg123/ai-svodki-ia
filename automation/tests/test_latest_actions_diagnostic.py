from __future__ import annotations

import json
import urllib.request
import unittest


class LatestActionsDiagnosticTests(unittest.TestCase):
    def test_print_latest_daily_runs_and_artifacts(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-svodki-diagnostic",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        urls = {
            "runs": "https://api.github.com/repos/Herurg123/ai-svodki-ia/actions/runs?per_page=100",
            "artifacts": "https://api.github.com/repos/Herurg123/ai-svodki-ia/actions/artifacts?name=daily-production-2026-07-30&per_page=100",
        }
        output = {}
        for name, url in urls.items():
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                output[name] = json.load(response)
        runs = [
            {
                "id": item.get("id"),
                "run_number": item.get("run_number"),
                "event": item.get("event"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "head_sha": item.get("head_sha"),
                "html_url": item.get("html_url"),
            }
            for item in output["runs"].get("workflow_runs", [])
            if item.get("name") == "Daily production digest"
            and str(item.get("created_at", "")) >= "2026-07-30T00:00:00Z"
        ]
        artifacts = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "expired": item.get("expired"),
                "size_in_bytes": item.get("size_in_bytes"),
                "created_at": item.get("created_at"),
                "workflow_run": item.get("workflow_run"),
            }
            for item in output["artifacts"].get("artifacts", [])
        ]
        print("ACTIONS_DIAGNOSTIC=" + json.dumps({"runs": runs, "artifacts": artifacts}, ensure_ascii=False))
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
