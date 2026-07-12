from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_ROOT = ROOT / "automation" / "preview"
CONFIG_PATH = ROOT / "automation" / "config" / "site.json"
DEFAULT_REQUEST = ROOT / "automation" / "requests" / "image-preview.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверить фон и итоговую обложку image preview."
    )
    parser.add_argument(
        "--request",
        type=Path,
        default=DEFAULT_REQUEST,
        help="JSON-запрос на генерацию.",
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


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_size(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(f"Некорректный size: {value!r}") from exc
    return width, height


def inspect_png(path: Path, expected_size: tuple[int, int]) -> tuple[dict[str, Any], Image.Image]:
    if not path.is_file():
        raise RuntimeError(f"Не найден файл: {path}")
    if not path.read_bytes()[:8] == PNG_SIGNATURE:
        raise RuntimeError(f"Файл не имеет PNG-сигнатуры: {path.name}")

    try:
        with Image.open(path) as opened:
            opened.verify()
        with Image.open(path) as opened:
            opened.load()
            image = opened.convert("RGB")
    except Exception as exc:
        raise RuntimeError(f"Повреждённый PNG {path.name}: {exc}") from exc

    if image.size != expected_size:
        raise RuntimeError(
            f"{path.name}: размер {image.size}, ожидался {expected_size}."
        )

    stat = ImageStat.Stat(image.resize((256, 144)))
    mean_stddev = sum(stat.stddev) / len(stat.stddev)
    extrema = image.getextrema()
    dynamic_range = max(high - low for low, high in extrema)

    info = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "mean_stddev": round(mean_stddev, 3),
        "dynamic_range": dynamic_range,
    }
    return info, image


def changed_pixel_ratio(first: Image.Image, second: Image.Image) -> float:
    difference = ImageChops.difference(first, second).convert("L")
    histogram = difference.histogram()
    changed = sum(histogram[1:])
    total = first.width * first.height
    return changed / max(total, 1)


def main() -> int:
    args = parse_args()
    source_dir = resolve_from_root(args.source_dir)
    request_path = resolve_from_root(args.request)
    report_path = source_dir / "image-validation.json"
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}

    try:
        assert_inside_preview(source_dir)
        request = read_json(request_path)
        meta = read_json(source_dir / "meta.json")
        config = read_json(CONFIG_PATH)
        image_run = read_json(source_dir / "image-run-info.json")
        compose_run = read_json(source_dir / "cover-compose-info.json")

        if not all(isinstance(value, dict) for value in (request, meta, config, image_run, compose_run)):
            raise RuntimeError("Один из служебных JSON-файлов не является объектом.")

        publication_date = str(request.get("publication_date", ""))
        if source_dir.name != publication_date:
            errors.append("Имя source-dir не совпадает с publication_date.")
        if meta.get("date") != publication_date:
            errors.append("Дата meta.json не совпадает с запросом.")
        if image_run.get("status") != "ok":
            errors.append("image-run-info.json не имеет status=ok.")
        if compose_run.get("status") != "ok":
            errors.append("cover-compose-info.json не имеет status=ok.")
        if compose_run.get("title") != meta.get("title"):
            errors.append("Наложенный заголовок не совпадает с meta.title.")

        expected_cover = str(config.get("image_filename_template", "")).format(
            date=publication_date
        )
        if meta.get("cover_filename") != expected_cover:
            errors.append(
                "cover_filename не совпадает с шаблоном site.json: "
                f"{meta.get('cover_filename')!r} != {expected_cover!r}"
            )

        expected_size = parse_size(str(request.get("size", "")))
        art_info, art = inspect_png(source_dir / "cover-art.png", expected_size)
        cover_info, cover = inspect_png(source_dir / "cover.png", expected_size)
        details["cover_art"] = art_info
        details["cover"] = cover_info

        for info in (art_info, cover_info):
            if info["bytes"] < 8_000:
                errors.append(f"{info['filename']} подозрительно мал: {info['bytes']} байт.")
            if info["mean_stddev"] < 5:
                errors.append(f"{info['filename']} выглядит почти однотонным.")
            if info["dynamic_range"] < 30:
                errors.append(f"{info['filename']} имеет слишком малый динамический диапазон.")
            if info["bytes"] > 15 * 1024 * 1024:
                warnings.append(f"{info['filename']} больше 15 МБ.")

        if art_info["sha256"] == cover_info["sha256"]:
            errors.append("cover.png не отличается от cover-art.png.")

        changed_ratio = changed_pixel_ratio(art, cover)
        details["changed_pixel_ratio"] = round(changed_ratio, 6)
        if changed_ratio < 0.005:
            errors.append(
                "После композиции изменилось менее 0,5% пикселей; заголовок мог не наложиться."
            )
        if changed_ratio > 0.65:
            warnings.append(
                "Композиция изменила более 65% пикселей; затемнение может быть чрезмерным."
            )

        width, height = expected_size
        gcd = math.gcd(width, height)
        details["aspect_ratio"] = f"{width // gcd}:{height // gcd}"
        if width * 9 != height * 16:
            errors.append("Для текущего проекта ожидается точное соотношение сторон 16:9.")

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    report = {
        "status": "ok" if not errors else "error",
        "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_dir": str(source_dir.relative_to(ROOT)) if ROOT in source_dir.parents else str(source_dir),
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }
    atomic_write(report_path, pretty_json(report))

    if errors:
        print("Проверка изображения завершилась ошибками:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Image preview validation passed.")
    print(f"Предупреждений: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
