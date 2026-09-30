from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
NORMALIZER = SCRIPTS / "normalize_digest_artifact.py"
RECOVERY = SCRIPTS / "recover_digest_artifact.py"
WORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"

SAFE_PROMPT = (
    "Изображение 16:9: ИИ-Сводка на 30 сентября 2026.\n"
    "Главные визуальные темы: рабочие ИИ-агенты.\n"
    "Композиция: редакционная сцена.\n"
    "Стиль: без логотипов; без дополнительного текста; "
    "без водяных знаков; без узнаваемых лиц."
)


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class Sep30MetaServiceRecoveryTests(unittest.TestCase):
    def _write_sep30_shape(self, root: Path) -> Path:
        artifact = root / "2026-09-30"
        artifact.mkdir()
        article = (
            "<p>Выпуск.</p>"
            "<h2>Мировые лидеры ИИ</h2>"
            "<h3>Обновление: Meta* расширила Muse на малый бизнес</h3>"
            "<p>Meta представила Muse.</p>"
            "<p><em>*Meta и ее сервисы - в России запрещены</em></p>"
        )
        digest = {
            "description": "Meta* расширяет Muse для малого бизнеса.",
            "article_html": article,
            "image_prompt": SAFE_PROMPT,
        }
        editorial = {
            "selection_summary": "Выбран сюжет про расширение Meta* в малый бизнес.",
            "digest": digest,
        }
        write_json(artifact / "digest.json", digest)
        write_json(artifact / "editorial-output.json", editorial)
        write_json(artifact / "editorial-output-raw.json", editorial)
        write_json(
            artifact / "meta.json",
            {"description": "Meta* расширяет Muse для малого бизнеса."},
        )
        write_json(
            artifact / "selection.json",
            {"selection_summary": "Выбран сюжет про Meta* и Muse."},
        )
        (artifact / "image-prompt.txt").write_text(SAFE_PROMPT, encoding="utf-8")
        return artifact

    def test_public_normalization_removes_only_service_meta_display_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self._write_sep30_shape(Path(tmp))
            report = artifact / "artifact-normalization.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(NORMALIZER),
                    "--artifact-dir",
                    str(artifact),
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)

            digest = json.loads((artifact / "digest.json").read_text(encoding="utf-8"))
            editorial = json.loads(
                (artifact / "editorial-output.json").read_text(encoding="utf-8")
            )
            meta = json.loads((artifact / "meta.json").read_text(encoding="utf-8"))
            selection = json.loads(
                (artifact / "selection.json").read_text(encoding="utf-8")
            )

            self.assertIn("Meta*", digest["article_html"])
            self.assertNotIn("Meta*", digest["description"])
            self.assertNotIn("Meta*", editorial["selection_summary"])
            self.assertNotIn("Meta*", editorial["digest"]["description"])
            self.assertNotIn("Meta*", meta["description"])
            self.assertNotIn("Meta*", selection["selection_summary"])

            payload = json.loads(report.read_text(encoding="utf-8"))
            changed = {
                (item.get("file"), item.get("field"))
                for item in payload.get("changes", [])
                if item.get("normalization") == "meta_service_marker"
            }
            self.assertIn(("meta.json", "$.description"), changed)
            self.assertIn(("selection.json", "$.selection_summary"), changed)

    def test_public_recovery_accepts_meta_service_error_for_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recovery_root = root / "recovery"
            source = recovery_root / "2026-09-30"
            source.mkdir(parents=True)
            write_json(
                source / "run-info.json",
                {
                    "publication_date": "2026-09-30",
                    "finished_at": "2026-09-30T01:00:00+00:00",
                    "research": {
                        "status": "ok",
                        "temporal_anchor_version": 1,
                        "response": {
                            "response_status": "completed",
                            "web_search_calls": 12,
                        },
                    },
                },
            )
            research = {
                "status": "ok",
                "publication_date": "2026-09-30",
                "search_window": {
                    "start_at": "2026-09-28T06:00:00+03:00",
                    "end_at": "2026-09-30T06:00:00+03:00",
                },
                "coverage": [],
                "candidates": [{"id": "cand-001"}],
            }
            write_json(source / "candidates.json", research)
            write_json(source / "research-output-raw.json", research)
            write_json(
                source / "artifact-validation.json",
                {
                    "status": "error",
                    "errors": [
                        {
                            "code": "meta_star_service_field",
                            "message": "Meta* найдено вне article_html",
                        }
                    ],
                },
            )
            report = root / "recovery-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RECOVERY),
                    "--recovery-root",
                    str(recovery_root),
                    "--target-dir",
                    str(root / "target"),
                    "--publication-date",
                    "2026-09-30",
                    "--timezone",
                    "Europe/Moscow",
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["recovery_mode"], "research_only")

    def test_recovery_workflow_has_same_run_checkpoint_fallback(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            'echo "fallback_artifact_name=${fallback_artifact_name}" >> "${GITHUB_OUTPUT}"',
            workflow,
        )
        restore_start = workflow.index("- name: Restore saved paid artifact")
        restore_end = workflow.index("- name: Install pinned OpenAI SDK", restore_start)
        restore = workflow[restore_start:restore_end]
        self.assertIn("RECOVERY_FALLBACK_ARTIFACT_NAME", restore)
        self.assertIn("gh run download", restore)
        self.assertIn("Безопасный checkpoint fallback", restore)
        self.assertIn(
            "Свежий paid research автоматически не запускается",
            restore,
        )


if __name__ == "__main__":
    unittest.main()
