from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_ROOT = ROOT / "automation" / "preview"
FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Наложить точный заголовок на сгенерированный фон."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Preview выпуска: automation/preview/YYYY-MM-DD/.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def resolve_from_root(path: Path) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    return candidate.resolve()


def assert_inside_preview(path: Path) -> None:
    resolved = path.resolve()
    allowed = PREVIEW_ROOT.resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise RuntimeError("source-dir должен находиться внутри automation/preview/.")
    if (ROOT / "posts").resolve() == resolved or (ROOT / "posts").resolve() in resolved.parents:
        raise RuntimeError("Рабочий каталог posts/ запрещён.")


def atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_font_path() -> Path:
    configured = os.getenv("COVER_FONT_PATH")
    candidates = ([Path(configured)] if configured else []) + list(FONT_CANDIDATES)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Не найден системный шрифт с поддержкой кириллицы. "
        "Ожидался DejaVu Sans Bold или Liberation Sans Bold."
    )


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_title(
    draw: ImageDraw.ImageDraw,
    title: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    words = title.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_title(
    draw: ImageDraw.ImageDraw,
    title: str,
    font_path: Path,
    width: int,
    height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    max_width = int(width * 0.82)
    max_height = int(height * 0.28)
    spacing_ratio = 0.18

    for size in range(int(height * 0.115), 43, -2):
        font = ImageFont.truetype(str(font_path), size=size)
        lines = wrap_title(draw, title, font, max_width)
        if not lines or len(lines) > 2:
            continue
        spacing = max(8, int(size * spacing_ratio))
        box = draw.multiline_textbbox(
            (0, 0),
            "\n".join(lines),
            font=font,
            spacing=spacing,
        )
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return font, lines, spacing

    raise RuntimeError("Не удалось вписать заголовок максимум в две строки.")


def build_top_gradient(width: int, height: int) -> Image.Image:
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = overlay.load()
    fade_height = max(1, int(height * 0.52))
    for y in range(fade_height):
        progress = y / max(fade_height - 1, 1)
        alpha = int(218 * (1.0 - progress) ** 1.7)
        for x in range(width):
            horizontal = 1.0 - 0.28 * (x / max(width - 1, 1))
            pixels[x, y] = (4, 8, 18, int(alpha * horizontal))
    return overlay


def main() -> int:
    args = parse_args()
    source_dir = resolve_from_root(args.source_dir)
    report_path = source_dir / "cover-compose-info.json"
    report: dict[str, Any] = {
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": None,
        "font": None,
        "font_size": None,
        "lines": None,
        "input_sha256": None,
        "output_sha256": None,
        "output_bytes": None,
        "error": None,
    }

    try:
        assert_inside_preview(source_dir)
        meta = read_json(source_dir / "meta.json")
        if not isinstance(meta, dict):
            raise RuntimeError("meta.json должен содержать JSON-объект.")

        title = str(meta.get("title", "")).strip()
        if not title:
            raise RuntimeError("В meta.json отсутствует title.")
        report["title"] = title

        art_path = source_dir / "cover-art.png"
        output_path = source_dir / "cover.png"
        if not art_path.is_file():
            raise RuntimeError("Не найден cover-art.png.")

        font_path = find_font_path()
        report["font"] = font_path.name
        report["input_sha256"] = sha256_file(art_path)

        with Image.open(art_path) as opened:
            opened.load()
            base = opened.convert("RGBA")

        width, height = base.size
        composed = Image.alpha_composite(base, build_top_gradient(width, height))

        # Отдельный слой даёт аккуратную тень без изменения исходного фона.
        text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)
        font, lines, spacing = fit_title(draw, title, font_path, width, height)
        report["font_size"] = font.size
        report["lines"] = lines

        text = "\n".join(lines)
        x = int(width * 0.064)
        y = int(height * 0.075)

        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.multiline_text(
            (x + 4, y + 5),
            text,
            font=font,
            fill=(0, 0, 0, 210),
            spacing=spacing,
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=5))
        composed = Image.alpha_composite(composed, shadow_layer)

        draw.multiline_text(
            (x, y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            spacing=spacing,
        )

        accent_y = y + int(font.size * len(lines) * 1.18) + spacing * (len(lines) - 1)
        draw.rounded_rectangle(
            (x, accent_y, x + int(width * 0.12), accent_y + max(6, int(height * 0.009))),
            radius=5,
            fill=(255, 255, 255, 220),
        )

        composed = Image.alpha_composite(composed, text_layer).convert("RGB")
        temporary = output_path.with_suffix(".png.tmp")
        composed.save(temporary, format="PNG", optimize=True)
        temporary.replace(output_path)

        report.update(
            {
                "status": "ok",
                "output_sha256": sha256_file(output_path),
                "output_bytes": output_path.stat().st_size,
            }
        )
        atomic_write_text(report_path, pretty_json(report))

        print(f"Обложка собрана: {output_path.relative_to(ROOT)}")
        print(f"Заголовок: {title}")
        print(f"Шрифт: {font_path.name}, размер: {font.size}")
        return 0

    except Exception as exc:
        report["status"] = "error"
        report["error"] = f"{type(exc).__name__}: {exc}"[:4000]
        try:
            source_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_text(report_path, pretty_json(report))
        except Exception:
            pass
        print(report["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
