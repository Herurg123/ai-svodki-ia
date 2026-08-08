from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
import sys
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("repository_hygiene", SCRIPT_DIR / "repository_hygiene.py")
assert SPEC and SPEC.loader
rh = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rh
SPEC.loader.exec_module(rh)

REPO = "Herurg123/ai-svodki-ia"


def pr(number, branch, sha, *, merged_at=None, state="closed", updated_at=None, merge_sha=None):
    return {
        "number": number,
        "state": state,
        "merged_at": merged_at,
        "updated_at": updated_at or merged_at or "2026-08-01T00:00:00Z",
        "created_at": "2026-07-01T00:00:00Z",
        "merge_commit_sha": merge_sha,
        "head": {"ref": branch, "sha": sha, "repo": {"full_name": REPO}},
    }


class RepositoryHygieneTests(unittest.TestCase):
    def test_recent_merge_window_uses_merged_at_not_pr_number(self):
        items = [
            pr(100, "a", "a"*40, merged_at="2026-08-01T00:00:00Z"),
            pr(2, "b", "b"*40, merged_at="2026-08-03T00:00:00Z"),
        ]
        self.assertEqual([p["number"] for p in rh.merged_sorted(items)], [2, 100])

    def test_branch_safety_requires_old_merged_unchanged_head(self):
        old = pr(10, "agent/old", "1"*40, merged_at="2026-07-01T00:00:00Z")
        recent = pr(20, "agent/recent", "2"*40, merged_at="2026-08-01T00:00:00Z")
        abandoned = pr(9, "agent/abandoned", "3"*40, state="closed", merged_at=None)
        all_prs = [old, recent, abandoned]
        cls, _, _ = rh.classify_branch(
            {"name":"agent/old", "protected":False, "commit":{"sha":"1"*40}},
            repository=REPO, default_branch="main", prs=all_prs, recent_numbers={20}
        )
        self.assertEqual(cls, "safe_delete")
        cls, _, _ = rh.classify_branch(
            {"name":"agent/recent", "protected":False, "commit":{"sha":"2"*40}},
            repository=REPO, default_branch="main", prs=all_prs, recent_numbers={20}
        )
        self.assertEqual(cls, "protected")
        cls, _, _ = rh.classify_branch(
            {"name":"agent/abandoned", "protected":False, "commit":{"sha":"3"*40}},
            repository=REPO, default_branch="main", prs=all_prs, recent_numbers={20}
        )
        self.assertEqual(cls, "review_only")
        cls, reason, _ = rh.classify_branch(
            {"name":"agent/old", "protected":False, "commit":{"sha":"4"*40}},
            repository=REPO, default_branch="main", prs=all_prs, recent_numbers={20}
        )
        self.assertEqual((cls, reason), ("review_only", "branch_diverged_after_merge"))
        cls, reason, _ = rh.classify_branch(
            {"name":"agent/old", "protected":False, "commit":{"sha":"1"*40}},
            repository=REPO, default_branch="main", prs=all_prs, recent_numbers={20},
            active_branches={"agent/old"},
        )
        self.assertEqual((cls, reason), ("protected", "active_actions_run"))

    def test_workflow_grace_and_pages_special_case(self):
        canonical = {".github/workflows/ci.yml"}
        base = {"id":1, "path":".github/workflows/ci.yml"}
        self.assertEqual(rh.classify_workflow(base, canonical, False, {}, {}, [])[0], "protected")
        pages = {"id":2, "path":"dynamic/pages/pages-build-deployment"}
        self.assertEqual(rh.classify_workflow(pages, canonical, False, {}, {}, [])[0], "safe_disable")
        orphan = {"id":3, "path":".github/workflows/temporary.yml"}
        runs = [{"head_branch":"agent/old", "created_at":"2026-08-01T00:00:00Z"}]
        self.assertEqual(rh.classify_workflow(orphan, canonical, False, {}, {"agent/old":"safe_delete"}, runs)[0], "safe_disable")
        self.assertEqual(rh.classify_workflow(orphan, canonical, False, {}, {"agent/old":"protected"}, runs)[0], "protected")
        active_runs = [{"head_branch":"agent/old", "created_at":"2026-08-01T00:00:00Z", "status":"in_progress"}]
        cls, reason = rh.classify_workflow(orphan, canonical, False, {}, {"agent/old":"safe_delete"}, active_runs)
        self.assertEqual((cls, reason), ("protected", "workflow_has_active_run"))
        old_queued = {"status":"queued", "created_at":"2026-07-03T00:00:00Z"}
        now = rh.dt.datetime(2026, 8, 8, tzinfo=rh.dt.timezone.utc)
        self.assertFalse(rh.live_run(old_queued, now))

    def test_production_artifact_windows(self):
        def artifact(i, run):
            return {"id":i, "created_at":f"2026-08-0{i%9+1}T00:00:00Z", "workflow_run":{"id":run}}
        dates = ["2026-08-08","2026-08-07","2026-08-06","2026-08-05","2026-08-04","2026-08-03"]
        groups = {
            "2026-08-08":[artifact(1,11), artifact(2,12)],
            "2026-08-06":[artifact(3,30), artifact(4,31)],
            "2026-08-03":[artifact(5,50)],
            "2026-08-09":[artifact(6,60)],
            "2026-08-01":[artifact(7,70)],
        }
        result = rh.classify_production(groups, dates, {30})
        self.assertEqual(result[1][0], "protected")
        self.assertEqual(result[2][0], "protected")
        self.assertEqual(result[3], ("protected", "final_publish_artifact"))
        self.assertEqual(result[4][0], "safe_delete")
        self.assertEqual(result[5][0], "safe_delete")
        self.assertEqual(result[6][0], "protected")
        self.assertEqual(result[7][0], "review_only")

    def test_ci_artifact_keeps_only_protected_shas(self):
        artifact = {"name":"main-ci-" + "a"*40, "workflow_run":{"head_branch":"agent/x"}}
        self.assertEqual(rh.classify_ci(artifact, {"a"*40}, {}, {})[0], "protected")
        self.assertEqual(rh.classify_ci(artifact, set(), {"agent/x":"safe_delete"}, {})[0], "safe_delete")
        self.assertEqual(rh.classify_ci(artifact, set(), {"agent/x":"protected"}, {})[0], "safe_delete")
        self.assertEqual(rh.classify_ci(artifact, set(), {"agent/x":"review_only"}, {})[0], "review_only")
        self.assertEqual(rh.classify_ci(artifact, set(), {}, {})[0], "review_only")
        main_artifact = {"name":"main-ci-" + "b"*40, "workflow_run":{"head_branch":"main"}}
        self.assertEqual(rh.classify_ci(main_artifact, set(), {"main":"protected"}, {})[0], "safe_delete")

    def test_rss_dates_are_unique_and_descending(self):
        text = "https://x/posts/2026-08-07/ x https://x/posts/2026-08-08/ https://x/posts/2026-08-07/"
        self.assertEqual(rh.publication_dates(text), ["2026-08-08","2026-08-07"])

    def test_build_plan_smoke_with_fake_api(self):
        class FakeApi:
            repository = REPO
            def repo(self): return {"default_branch":"main", "has_pages":False}
            def branch(self, name):
                if name == "main": return {"name":"main", "protected":False, "commit":{"sha":"f"*40}}
                if name == "agent/old": return {"name":"agent/old", "protected":False, "commit":{"sha":"1"*40}}
                return None
            def prs(self, state, base=None):
                old = pr(10, "agent/old", "1"*40, merged_at="2026-07-01T00:00:00Z", merge_sha="9"*40)
                recent = [pr(20+i, f"agent/recent-{i}", str(i)*40, merged_at=f"2026-08-0{i+1}T00:00:00Z", merge_sha="8"*40) for i in range(5)]
                return [] if state == "open" else [old, *recent]
            def runs(self, status): return []
            def branches(self): return [self.branch("main"), self.branch("agent/old")]
            def contents(self, path, ref="main"):
                if path == ".github/workflows": return [{"type":"file", "path":".github/workflows/ci.yml"}]
                raise AssertionError(path)
            def workflows(self): return [{"id":1,"name":"Main CI","path":".github/workflows/ci.yml","state":"active"}]
            def workflow_runs(self, workflow_id, limit=100): return []
            def file_text(self, path, ref="main"): return '<link>https://x/posts/2026-08-08/</link>'
            def artifacts(self): return []
            def jobs(self, run_id): return []
        with tempfile.TemporaryDirectory() as tmp:
            plan = rh.build_plan(FakeApi(), Path(tmp))
        old = next(item for item in plan["branches"] if item["name"] == "agent/old")
        self.assertEqual(old["classification"], "safe_delete")
        self.assertEqual(plan["workflows"][0]["classification"], "protected")
        self.assertEqual(plan["publication_dates"], ["2026-08-08"])


if __name__ == "__main__":
    unittest.main()
