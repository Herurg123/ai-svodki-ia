from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_ROOT = ROOT / "automation" / "preview"
DEFAULT_REQUEST = ROOT / "automation" / "requests" / "image-preview.json"
DEFAULT_MODEL = "gpt-image-2"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ALLOWED_QUALITIES = {"low", "medium", "high"}
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Создать одно изображение-фон через OpenAI Image API "
            "и сохранить его только в automation/preview/."
        )
    )
    parser.add_argument(
        "--request",
        type=Path,
        default=DEFAULT_REQUEST,
        help="JSON-запрос на генерацию изображения.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=(
            "Preview выпуска. По умолчанию "
            "automation/preview/<publication_date>/."
        ),
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
        raise RuntimeError(
            "Результат разрешено сохранять только внутри automation/preview/<date>/."
        )
    if (ROOT / "posts").resolve() == resolved or (ROOT / "posts").resolve() in resolved.parents:
        raise RuntimeError("Рабочий каталог posts/ запрещён для image preview.")


def parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{2,4})x(\d{2,4})", value)
    if not match:
        raise RuntimeError("size должен иметь формат WIDTHxHEIGHT, например 1536x864.")

    width, height = map(int, match.groups())
    pixels = width * height
    long_edge = max(width, height)
    short_edge = min(width, height)

    if width % 16 or height % 16:
        raise RuntimeError("Обе стороны изображения должны быть кратны 16 пикселям.")
    if long_edge > 3840:
        raise RuntimeError("Максимальная сторона изображения не должна превышать 3840 px.")
    if long_edge / short_edge > 3:
        raise RuntimeError("Соотношение длинной и короткой стороны не должно превышать 3:1.")
    if not 655_360 <= pixels <= 8_294_400:
        raise RuntimeError(
            "Число пикселей должно находиться в диапазоне 655360..8294400."
        )

    return width, height


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("Файл запроса должен содержать JSON-объект.")

    allowed = {"enabled", "publication_date", "request_id", "size", "quality"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise RuntimeError("Неизвестные поля запроса: " + ", ".join(unknown))

    if value.get("enabled") is not True:
        raise RuntimeError("Для платного запуска поле enabled должно быть равно true.")

    publication_date = str(value.get("publication_date", ""))
    try:
        parsed_date = date.fromisoformat(publication_date)
    except ValueError as exc:
        raise RuntimeError("publication_date должна иметь формат YYYY-MM-DD.") from exc
    if parsed_date.isoformat() != publication_date:
        raise RuntimeError("publication_date должна иметь строгий формат YYYY-MM-DD.")

    request_id = str(value.get("request_id", ""))
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        raise RuntimeError(
            "request_id должен содержать 1–80 букв, цифр, точек, дефисов или подчёркиваний."
        )

    size = str(value.get("size", ""))
    parse_size(size)

    quality = str(value.get("quality", ""))
    if quality not in ALLOWED_QUALITIES:
        raise RuntimeError("quality должна быть low, medium или high.")

    return {
        "enabled": True,
        "publication_date": publication_date,
        "request_id": request_id,
        "size": size,
        "quality": quality,
    }


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sdk_version() -> str:
    try:
        return package_version("openai")
    except PackageNotFoundError:
        return "unknown"


def to_plain_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    return str(value)


def sanitize_error(exc: Exception, api_key: str | None) -> str:
    message = f"{type(exc).__name__}: {exc}"
    if api_key:
        message = message.replace(api_key, "***")
    return message[:4000]


def prepare_visual_prompt(raw_prompt: str, title: str) -> str:
    text = " ".join(raw_prompt.strip().split())
    if not text:
        raise RuntimeError("image-prompt.txt пуст.")

    # Убираем точный заголовок и положительные инструкции о его рисовании.
    text = text.replace(f"«{title}»", "")
    text = text.replace(f'"{title}"', "")
    text = text.replace(title, "")

    sentences = re.split(r"(?<=[.!?])\s+", text)
    filtered: list[str] = []
    for sentence in sentences:
        lowered = sentence.casefold()
        if "заголов" in lowered and "без заголов" not in lowered:
            continue
        if "крупный текст" in lowered and "без крупного текста" not in lowered:
            continue
        cleaned = re.sub(r"\s+", " ", sentence).strip(" ,.;:-")
        if cleaned:
            filtered.append(cleaned)

    visual = ". ".join(filtered).strip()
    if visual and not visual.endswith((".", "!", "?")):
        visual += "."

    suffix = (
        " Создай только визуальный фон редакционной обложки. "
        "Не рисуй никаких букв, слов, цифр, дат, подписей, интерфейсного текста, "
        "логотипов или водяных знаков. "
        "Оставь спокойную контрастную свободную область в верхней левой части "
        "для последующего программного наложения заголовка. "
        "Ключевые визуальные объекты не размещай вплотную к краям."
    )
    return (visual + suffix).strip()


def main() -> int:
    args = parse_args()
    request_path = resolve_from_root(args.request)
    api_key = os.getenv("OPENAI_API_KEY")
    model = (os.getenv("OPENAI_IMAGE_MODEL") or DEFAULT_MODEL).strip()
    started_at = datetime.now(timezone.utc)

    report: dict[str, Any] = {
        "status": "running",
        "request_id": None,
        "publication_date": None,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "model_requested": model,
        "size": None,
        "quality": None,
        "output_format": "png",
        "api_request_id": None,
        "openai_sdk_version": sdk_version(),
        "usage": None,
        "revised_prompt": None,
        "effective_prompt_sha256": None,
        "image_sha256": None,
        "image_bytes": None,
        "error": None,
    }

    source_dir: Path | None = None

    try:
        request = validate_request(read_json(request_path))
        report.update(
            {
                "request_id": request["request_id"],
                "publication_date": request["publication_date"],
                "size": request["size"],
                "quality": request["quality"],
            }
        )

        if args.source_dir is None:
            source_dir = PREVIEW_ROOT / request["publication_date"]
        else:
            source_dir = resolve_from_root(args.source_dir)
        source_dir = source_dir.resolve()
        assert_inside_preview(source_dir)

        if source_dir.name != request["publication_date"]:
            raise RuntimeError(
                "Имя source-dir должно совпадать с publication_date из запроса."
            )

        meta = read_json(source_dir / "meta.json")
        if not isinstance(meta, dict):
            raise RuntimeError("meta.json должен содержать JSON-объект.")
        if meta.get("date") != request["publication_date"]:
            raise RuntimeError("Дата meta.json не совпадает с image-preview.json.")

        title = str(meta.get("title", "")).strip()
        if not title:
            raise RuntimeError("В meta.json отсутствует title.")

        raw_prompt = (source_dir / "image-prompt.txt").read_text(
            encoding="utf-8"
        )
        effective_prompt = prepare_visual_prompt(raw_prompt, title)
        report["effective_prompt_sha256"] = hashlib.sha256(
            effective_prompt.encode("utf-8")
        ).hexdigest()

        if not api_key:
            raise RuntimeError("Переменная окружения OPENAI_API_KEY не задана.")
        if not model:
            raise RuntimeError("OPENAI_IMAGE_MODEL не должен быть пустым.")

        output_path = source_dir / "cover-art.png"
        report_path = source_dir / "image-run-info.json"
        for stale in (output_path, report_path):
            if stale.exists():
                stale.unlink()

        # max_retries=0 принципиален: один запуск workflow делает не более одного
        # платного запроса. Повтор выполняется только новым request_id.
        client = OpenAI(api_key=api_key, timeout=600.0, max_retries=0)
        result = client.images.generate(
            model=model,
            prompt=effective_prompt,
            size=request["size"],
            quality=request["quality"],
            n=1,
        )

        if not getattr(result, "data", None):
            raise RuntimeError("Image API вернул пустой массив data.")
        first = result.data[0]
        encoded = getattr(first, "b64_json", None)
        if not encoded:
            raise RuntimeError("Image API не вернул data[0].b64_json.")

        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Image API вернул некорректный base64.") from exc

        if not image_bytes.startswith(PNG_SIGNATURE):
            raise RuntimeError("Ответ Image API не является PNG-файлом.")

        atomic_write_bytes(output_path, image_bytes)

        report.update(
            {
                "status": "ok",
                "finished_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "api_request_id": getattr(result, "_request_id", None),
                "usage": to_plain_dict(getattr(result, "usage", None)),
                "revised_prompt": getattr(first, "revised_prompt", None),
                "image_sha256": sha256_bytes(image_bytes),
                "image_bytes": len(image_bytes),
            }
        )
        atomic_write_text(report_path, pretty_json(report))

        print(f"Фон создан: {output_path.relative_to(ROOT)}")
        print(f"Модель: {model}")
        print(f"Размер: {request['size']}, качество: {request['quality']}")
        print("Платных запросов Image API в этом запуске: 1")
        return 0

    except Exception as exc:
        report["status"] = "error"
        report["finished_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        report["error"] = sanitize_error(exc, api_key)

        if source_dir is not None:
            try:
                assert_inside_preview(source_dir)
                source_dir.mkdir(parents=True, exist_ok=True)
                atomic_write_text(
                    source_dir / "image-run-info.json",
                    pretty_json(report),
                )
            except Exception:
                pass

        print(report["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
