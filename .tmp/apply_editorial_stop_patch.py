from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one occurrence, got {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_runtime() -> None:
    path = ROOT / "automation/scripts/ensure_story_coverage.py"
    marker = "\ndef main() -> int:\n"
    helper = r'''

def _promote_completed_zero_pool_editorial_stop(report_path: Path | None) -> bool:
    """Convert only a proven complete zero-pool audit into a healthy no-publish stop."""
    if report_path is None or not report_path.is_file():
        return False
    try:
        payload = read_json(report_path)
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    pool_after = payload.get("candidate_pool_after")
    api = payload.get("api") or {}
    error = str(payload.get("error") or "")
    terminal = bool(
        payload.get("status") == "error"
        and "После основного и дополнительного поиска не осталось ни одного достойного сюжета" in error
        and payload.get("audit_state") == "completed_usable"
        and not payload.get("audit_error")
        and not payload.get("validation_error")
        and payload.get("web_search_performed") is True
        and isinstance(api, dict)
        and api.get("status") == "completed"
        and payload.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(payload.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
        and payload.get("temporal_anchor_version") == TEMPORAL_ANCHOR_VERSION
        and _completed_sentinel_evidence(payload)
        and isinstance(pool_after, dict)
        and pool_after.get("total") == 0
    )
    if not terminal:
        return False
    payload["status"] = "editorial_stop"
    payload["editorial_stop"] = True
    payload["publication_mode"] = "none"
    payload["mode"] = "completed_zero_pool_editorial_stop"
    payload["editorial_stop_reason"] = (
        "Полный research, шесть обязательных coverage-проходов и актуальный "
        "recall sentinel не нашли ни одного достойного сюжета."
    )
    payload["error"] = None
    write_json(report_path, payload)
    return True
'''
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        raise RuntimeError("runtime main marker not found")
    text = text.replace(marker, helper + marker, 1)
    old_main = '''def main() -> int:\n    _set_last_recall_sentinel(None)\n    _sync_policy_overrides()\n    result = int(_base.main())\n    # _base.main() resets and then populates the shared sentinel diagnostics.\n    _set_last_recall_sentinel(_base._LAST_RECALL_SENTINEL)\n    return result\n'''
    new_main = '''def main() -> int:\n    _set_last_recall_sentinel(None)\n    _sync_policy_overrides()\n    result = int(_base.main())\n    # _base.main() resets and then populates the shared sentinel diagnostics.\n    _set_last_recall_sentinel(_base._LAST_RECALL_SENTINEL)\n    if result != 0 and _promote_completed_zero_pool_editorial_stop(_base._report_path()):\n        return 0\n    return result\n'''
    if text.count(old_main) != 1:
        raise RuntimeError("runtime main body not found exactly once")
    path.write_text(text.replace(old_main, new_main, 1), encoding="utf-8")


def patch_summary() -> None:
    path = ROOT / "automation/scripts/summarize_production_status.py"
    replace_once(
        path,
        '''    audit = (\n        isinstance(coverage, dict)\n        and coverage.get("status") == "ok"\n        and coverage.get("audit_status") in {"complete", "complete_with_gaps"}\n    )\n''',
        '''    audit = (\n        isinstance(coverage, dict)\n        and coverage.get("status") in {"ok", "editorial_stop"}\n        and coverage.get("audit_status") in {"complete", "complete_with_gaps"}\n    )\n''',
    )
    replace_once(
        path,
        '''def markdown_bool(value: bool) -> str:\n''',
        '''def completed_editorial_stop() -> bool:\n    coverage = read_json_if_exists(REPORT_ROOT / "coverage-audit.json")\n    if not isinstance(coverage, dict):\n        return False\n    pool = coverage.get("candidate_pool_after")\n    return bool(\n        coverage.get("status") == "editorial_stop"\n        and coverage.get("editorial_stop") is True\n        and coverage.get("audit_state") == "completed_usable"\n        and coverage.get("audit_status") in {"complete", "complete_with_gaps"}\n        and isinstance(pool, dict)\n        and pool.get("total") == 0\n    )\n\n\ndef markdown_bool(value: bool) -> str:\n''',
    )
    replace_once(
        path,
        '''    states = stage_state(publication_date)\n    success = job_status == "success"\n\n    if success:\n''',
        '''    states = stage_state(publication_date)\n    success = job_status == "success"\n    editorial_stop = completed_editorial_stop()\n\n    if success and editorial_stop:\n        lines = [\n            "## ⏸️ ИИ-Сводка: редакционная остановка",\n            "",\n            f"- **Дата выпуска:** `{publication_date}`",\n            "- **Результат:** штатный успешный no-publish",\n            "- **Причина:** полный research, обязательный coverage audit и актуальный recall sentinel не нашли достойных сюжетов",\n            "- **Commit:** не создавался",\n            "- **Image API:** не запускался после редакционной остановки",\n            "- **Deploy:** не запускался",\n            f"- **Recovery run ID:** `{recovery_run_id or 'нет'}`",\n            f"- **Run:** {run_url}",\n            "",\n            "### Этапы",\n            f"- Research: {markdown_bool(states['research'])}",\n            f"- Editorial: {markdown_bool(states['editorial'])}",\n            f"- Дополнительный поиск: {markdown_bool(states['coverage_audit'])}",\n            f"- Изображение: {markdown_bool(states['image'])}",\n            f"- Promotion: {markdown_bool(states['promoted'])}",\n        ]\n        lines.extend(coverage_audit_summary_lines())\n        return "\\n".join(lines) + "\\n", None\n\n    if success:\n''',
    )
    replace_once(
        path,
        '''            "status": (\n                "ok" if args.job_status == "success" else "error"\n            ),\n''',
        '''            "status": (\n                "editorial_stop"\n                if args.job_status == "success" and completed_editorial_stop()\n                else ("ok" if args.job_status == "success" else "error")\n            ),\n''',
    )


def patch_docs() -> None:
    root_readme = ROOT / "README.md"
    text = root_readme.read_text(encoding="utf-8")
    text = text.replace("`high_signal_recall_sentinel` версии 6", "`high_signal_recall_sentinel` версии 7")
    text = text.replace("high-signal recall sentinel v6", "high-signal recall sentinel v7")
    needle = "workflow создаёт\nпереиспользуемую редакционную остановку без публикации."
    replacement = needle + (" Такая остановка является\nштатным успешным `no-publish`: production остаётся зелёным, Image API, commit и\ndeploy не запускаются; красный статус сохраняется только для технически\nнеполного или ошибочного audit.")
    if needle not in text:
        raise RuntimeError("root README editorial-stop paragraph not found")
    text = text.replace(needle, replacement, 1)
    root_readme.write_text(text, encoding="utf-8")

    auto_readme = ROOT / "automation/README.md"
    text = auto_readme.read_text(encoding="utf-8")
    needle = "становится завершённой редакционной остановкой, которая переиспользуется без\nнового платного поиска."
    replacement = needle + (" Такая остановка завершает production успешно как `no-publish`;\nпосле неё не запускаются Image API, commit и deploy. Технически неполный audit\nпо-прежнему завершает job ошибкой.")
    if needle not in text:
        raise RuntimeError("automation README editorial-stop paragraph not found")
    auto_readme.write_text(text.replace(needle, replacement, 1), encoding="utf-8")

    agents = ROOT / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    section = '''\n## Editorial zero-pool stop\n\nA completed zero-pool result is a normal successful `no-publish`, not a\nproduction failure, but only after the current temporal-anchor contract, all\nsix mandatory coverage directions, and the current recall sentinel have\ncompleted successfully with no publishable candidate. In that state Image API,\ncommit, and deploy must remain skipped. Technical partial/error audits remain\nfail-closed and red. Recovery must reuse a proven completed editorial stop\nwithout repeating paid research or coverage.\n'''
    if "## Editorial zero-pool stop" not in text:
        text = text.rstrip() + "\n" + section
    agents.write_text(text, encoding="utf-8")


def patch_workflow_copy() -> None:
    source = ROOT / ".github/workflows/daily-production.yml"
    text = source.read_text(encoding="utf-8")
    old = '''    outputs:\n      publish: ${{ steps.mode.outputs.publish }}\n      commit_sha: ${{ steps.commit.outputs.commit_sha }}\n'''
    new = '''    outputs:\n      publish: ${{ steps.mode.outputs.publish }}\n      commit_sha: ${{ steps.commit.outputs.commit_sha }}\n      editorial_stop: ${{ steps.coverage.outputs.editorial_stop }}\n'''
    if text.count(old) != 1:
        raise RuntimeError("production outputs block not found")
    text = text.replace(old, new, 1)
    old = '''              and data.get("status") == "error"\n              and data.get("web_search_performed") is True\n'''
    new = '''              and data.get("status") in {"error", "editorial_stop"}\n              and data.get("audit_state") == "completed_usable"\n              and not data.get("audit_error")\n              and not data.get("validation_error")\n              and data.get("web_search_performed") is True\n'''
    if text.count(old) != 1:
        raise RuntimeError("terminal reuse predicate not found")
    text = text.replace(old, new, 1)
    old = '''      - name: Complete mandatory coverage audit for a short digest\n        if: steps.terminal_reuse.outputs.stop != 'true'\n'''
    new = '''      - name: Complete mandatory coverage audit for a short digest\n        id: coverage\n        if: steps.terminal_reuse.outputs.stop != 'true'\n'''
    if text.count(old) != 1:
        raise RuntimeError("coverage step marker not found")
    text = text.replace(old, new, 1)
    marker = '''          PY\n      - name: Normalize and validate digest artifact\n'''
    output_block = '''          PY\n          python - <<'PY'\n          import json\n          import os\n          from pathlib import Path\n          path = Path("automation/preview/production-daily/coverage-audit.json")\n          report = json.loads(path.read_text(encoding="utf-8"))\n          editorial_stop = bool(\n              report.get("status") == "editorial_stop"\n              and report.get("editorial_stop") is True\n              and report.get("audit_state") == "completed_usable"\n              and report.get("audit_status") in {"complete", "complete_with_gaps"}\n              and isinstance(report.get("candidate_pool_after"), dict)\n              and report["candidate_pool_after"].get("total") == 0\n          )\n          with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:\n              stream.write(\n                  "editorial_stop=" + ("true" if editorial_stop else "false") + "\\n"\n              )\n          if editorial_stop:\n              print("Completed zero-pool editorial stop: publication stages will be skipped.")\n          PY\n      - name: Normalize and validate digest artifact\n'''
    if text.count(marker) != 1:
        raise RuntimeError(f"post-coverage marker count={text.count(marker)}")
    text = text.replace(marker, output_block, 1)

    split_marker = "      - name: Normalize and validate digest artifact\n"
    before, after = text.split(split_marker, 1)
    after = split_marker + after
    guard = "steps.terminal_reuse.outputs.stop != 'true'"
    guarded = guard + " && steps.coverage.outputs.editorial_stop != 'true'"
    after = after.replace(guard, guarded)
    # Status summary must still run for a healthy editorial stop.
    after = after.replace(
        "if: always() && " + guarded,
        "if: always() && " + guard,
    )
    text = before + after

    target = ROOT / ".tmp/patched-daily-production.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def create_tests() -> None:
    path = ROOT / "automation/tests/test_editorial_stop_semantics.py"
    path.write_text(r'''from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load_module("editorial_stop_coverage", SCRIPTS / "ensure_story_coverage.py")
summary = load_module("editorial_stop_summary", SCRIPTS / "summarize_production_status.py")


def complete_zero_report() -> dict[str, object]:
    return {
        "status": "error",
        "error": "RuntimeError: После основного и дополнительного поиска не осталось ни одного достойного сюжета",
        "audit_state": "completed_usable",
        "audit_error": None,
        "validation_error": None,
        "web_search_performed": True,
        "api": {"status": "completed"},
        "audit_status": "complete_with_gaps",
        "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
        "temporal_anchor_version": coverage.TEMPORAL_ANCHOR_VERSION,
        "recall_sentinel": {
            "status": "complete_with_gaps",
            "version": coverage.RECALL_SENTINEL_VERSION,
            "search_strategy": coverage.RECALL_SENTINEL_STRATEGY,
        },
        "candidate_pool_after": {"total": 0, "world": 0, "russia": 0},
        "audit_needed": True,
        "search_budget": {"completed_calls": 7, "maximum_calls": 7},
        "required_directions": list(coverage.AUDIT_DIRECTION_IDS),
        "partial_directions": [],
        "unchecked_directions": [],
        "audit_added_candidates": 0,
    }


class EditorialStopRuntimeTests(unittest.TestCase):
    def test_complete_zero_pool_becomes_healthy_editorial_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "coverage-audit.json"
            report.write_text(json.dumps(complete_zero_report()), encoding="utf-8")
            self.assertTrue(coverage._promote_completed_zero_pool_editorial_stop(report))
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "editorial_stop")
            self.assertTrue(payload["editorial_stop"])
            self.assertEqual(payload["publication_mode"], "none")
            self.assertEqual(payload["mode"], "completed_zero_pool_editorial_stop")
            self.assertIsNone(payload["error"])

    def test_incomplete_audit_is_never_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "coverage-audit.json"
            payload = complete_zero_report()
            payload["audit_state"] = "completed_unusable"
            payload["audit_status"] = "partial"
            report.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(coverage._promote_completed_zero_pool_editorial_stop(report))
            unchanged = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(unchanged["status"], "error")

    def test_current_sentinel_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "coverage-audit.json"
            payload = complete_zero_report()
            payload["recall_sentinel"]["version"] = coverage.RECALL_SENTINEL_VERSION - 1
            report.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(coverage._promote_completed_zero_pool_editorial_stop(report))


class EditorialStopSummaryTests(unittest.TestCase):
    def test_successful_editorial_stop_has_non_error_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_root = Path(temp_dir) / "production-daily"
            report_root.mkdir(parents=True)
            payload = complete_zero_report()
            payload.update({"status": "editorial_stop", "editorial_stop": True, "error": None})
            (report_root / "coverage-audit.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            with mock.patch.object(summary, "REPORT_ROOT", report_root):
                markdown, annotation = summary.build_summary(
                    job_status="success",
                    publication_date="2026-08-09",
                    publish="true",
                    recovery_run_id="31299732706",
                    run_url="https://example.test/run",
                    commit_sha="",
                )
            self.assertIn("редакционная остановка", markdown)
            self.assertIn("штатный успешный no-publish", markdown)
            self.assertIn("Commit:** не создавался", markdown)
            self.assertIsNone(annotation)


class EditorialStopWorkflowContractTests(unittest.TestCase):
    def test_workflow_skips_post_coverage_publication_stages(self) -> None:
        workflow = (ROOT / ".github/workflows/daily-production.yml").read_text(encoding="utf-8")
        self.assertIn("id: coverage", workflow)
        self.assertIn("editorial_stop: ${{ steps.coverage.outputs.editorial_stop }}", workflow)
        self.assertIn(
            'data.get("status") in {"error", "editorial_stop"}', workflow
        )
        guard = "steps.coverage.outputs.editorial_stop != 'true'"
        self.assertGreaterEqual(workflow.count(guard), 9)
        for stage in (
            "Normalize and validate digest artifact",
            "Generate one production cover",
            "Build and validate candidate site",
            "Dry-run or promote candidate",
            "Commit production release",
        ):
            index = workflow.index(f"- name: {stage}")
            block = workflow[index : index + 500]
            self.assertIn(guard, block, stage)

    def test_docs_define_green_no_publish_contract(self) -> None:
        docs = "\n".join(
            [
                (ROOT / "README.md").read_text(encoding="utf-8"),
                (ROOT / "automation/README.md").read_text(encoding="utf-8"),
                (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            ]
        )
        self.assertIn("штатным успешным `no-publish`", docs)
        self.assertIn("Technical partial/error audits remain", docs)
        self.assertIn("recall sentinel v7", docs)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")


def main() -> None:
    patch_runtime()
    patch_summary()
    patch_docs()
    patch_workflow_copy()
    create_tests()


if __name__ == "__main__":
    main()
