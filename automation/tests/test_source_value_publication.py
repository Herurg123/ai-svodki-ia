import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_value_publication import load_publication, verify_page


class PublicationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "--quiet")
        base = self.repo / "automation/content/2026-09-08"
        base.mkdir(parents=True)
        for name in ["source-pulse.json", "candidates.json", "editorial-output.json", "stories.json"]:
            (base / name).write_text("[]" if name == "stories.json" else "{}")
        post = self.repo / "posts/2026-09-08/index.html"
        post.parent.mkdir(parents=True)
        post.write_text("<html>Committed release</html>")
        self.commit = self.commit_all()
        self.git("update-ref", "refs/remotes/origin/main", self.commit)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL).decode().strip()

    def commit_all(self):
        self.git("add", ".")
        self.git("-c", "user.name=Offline test", "-c", "user.email=offline@example.invalid", "commit", "--quiet", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_reads_commit_not_worktree_and_does_not_assert_delivery(self):
        (self.repo / "automation/content/2026-09-08/source-pulse.json").write_text('{"draft":true}')
        pulse, _, evidence = load_publication(self.repo, self.commit, "2026-09-08")
        self.assertEqual(json.loads(pulse), {})
        self.assertEqual(evidence["ftp_delivery"], "unknown")

    def test_unmerged_commit_is_not_publication(self):
        (self.repo / "draft.txt").write_text("draft")
        draft = self.commit_all()
        with self.assertRaises(ValueError):
            load_publication(self.repo, draft, "2026-09-08")

    def test_bad_ref_and_missing_release_are_rejected(self):
        for commit, day in [("HEAD", "2026-09-08"), (self.commit, "2026-09-09"), (self.commit, "../../wrong")]:
            with self.subTest(commit=commit, day=day), self.assertRaises(ValueError):
                load_publication(self.repo, commit, day)

    def test_unrelated_committed_page_cannot_publish_a_story(self):
        story = {"headline": "Correct story", "sources": [{"url": "https://vendor.example/one"}]}
        (self.repo / "automation/content/2026-09-08/stories.json").write_text(json.dumps([story]))
        commit = self.commit_all()
        self.git("update-ref", "refs/remotes/origin/main", commit)
        with self.assertRaises(ValueError):
            load_publication(self.repo, commit, "2026-09-08")
        (self.repo / "posts/2026-09-08/index.html").write_text('<h2>Correct story</h2><a href="https://vendor.example/one">Source</a>')
        commit = self.commit_all()
        self.git("update-ref", "refs/remotes/origin/main", commit)
        self.assertEqual(load_publication(self.repo, commit, "2026-09-08")[2]["commit"], commit)

    def test_script_text_is_not_a_visible_story(self):
        with self.assertRaises(ValueError):
            verify_page(b'<script>Correct story</script><a href="https://vendor.example/one">Source</a>', [{"headline": "Correct story", "sources": [{"url": "https://vendor.example/one"}]}])


if __name__ == "__main__":
    unittest.main()
