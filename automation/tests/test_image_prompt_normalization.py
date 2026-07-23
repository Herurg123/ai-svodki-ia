from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

from generate_digest_preview import normalize_image_prompt_constraints  # noqa: E402

IMAGE_CONFIG = json.loads(
    (ROOT / "automation" / "config" / "image.json").read_text(encoding="utf-8")
)


class ImagePromptNormalizationTests(unittest.TestCase):
    def test_missing_constraints_are_added_from_image_contract(self) -> None:
        digest = {
            "image_prompt": (
                "Изображение 16:9: точный заголовок «ИИ-Сводка на 24 июля 2026».\n"
                "Главные визуальные темы: вычислительная инфраструктура.\n"
                "Композиция: плотная редакционная сцена.\n"
                "Стиль: технологическая иллюстрация"
            )
        }

        changes = normalize_image_prompt_constraints(digest, IMAGE_CONFIG)

        self.assertEqual(len(changes), 1)
        prompt = digest["image_prompt"].casefold()
        for constraint in IMAGE_CONFIG["required_prompt_constraints"]:
            self.assertIn(constraint.casefold(), prompt)
        for constraint in IMAGE_CONFIG["recommended_prompt_constraints"]:
            self.assertIn(constraint.casefold(), prompt)
        self.assertIn(
            "без дополнительного текста, кроме точного заголовка",
            prompt,
        )
        self.assertIn("без узнаваемых лиц реальных людей", prompt)

    def test_complete_prompt_is_not_changed(self) -> None:
        constraints = [
            *IMAGE_CONFIG["required_prompt_constraints"],
            *IMAGE_CONFIG["recommended_prompt_constraints"],
        ]
        original = (
            "Изображение 16:9: точный заголовок «ИИ-Сводка на 24 июля 2026». "
            "Главные визуальные темы: инфраструктура. "
            "Композиция: плотная сцена. "
            "Стиль: редакционная графика. "
            + "; ".join(constraints)
            + "."
        )
        digest = {"image_prompt": original}

        changes = normalize_image_prompt_constraints(digest, IMAGE_CONFIG)

        self.assertEqual(changes, [])
        self.assertEqual(digest["image_prompt"], original)


if __name__ == "__main__":
    unittest.main()
