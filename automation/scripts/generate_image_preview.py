#!/usr/bin/env python3
"""Generate one artifact-only cover through the OpenAI Images API.

The script performs exactly one POST request and has no retry loop. It copies a
validated editorial fixture into an isolated output directory, writes only
artifact metadata, and never touches production posts/ or FTP.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "automation" / "config" / "image.json"
DEFAULT_API_URL = "https://api.openai.com/v1/images/generations"
OUTPUT_FILES = {
    "cover.png",
    "image-request.json",
    "image-manifest.json",
    "image-api-response.json",
    "cover-validation.json",
}


class ImageGenerationError(RuntimeError):
    """A safe error from the one-shot image generation stage."""


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ImageGenerationError(f"Не удалось прочитать {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ImageGenerationError(f"{label} содержит некорректный JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ImageGenerationError(f"{label} должен содержать JSON-объект")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_copy_source(source_dir: Path, output_dir: Path) -> list[str]:
    if not source_dir.is_dir():
        raise ImageGenerationError(f"Не найден source directory: {source_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in sorted(source_dir.iterdir()):
        if not path.is_file() or path.is_symlink():
            raise ImageGenerationError(f"Source должен содержать только обычные файлы: {path}")
        if path.name in OUTPUT_FILES:
            raise ImageGenerationError(f"Source уже содержит output Image API: {path.name}")
        destination = output_dir / path.name
        shutil.copy2(path, destination)
        copied.append(path.name)
    return copied


def parse_response_payload(payload: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ImageGenerationError("Images API должен вернуть ровно один data[] item")
    encoded = data[0].get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise ImageGenerationError("Images API не вернул data[0].b64_json")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ImageGenerationError("Images API вернул некорректный base64") from exc
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ImageGenerationError("Images API вернул данные без сигнатуры PNG")

    item = data[0]
    safe_metadata = {
        "created": payload.get("created"),
        "background": payload.get("background"),
        "output_format": payload.get("output_format"),
        "quality": payload.get("quality"),
        "size": payload.get("size"),
        "usage": payload.get("usage"),
        "data_count": 1,
        "revised_prompt": item.get("revised_prompt"),
    }
    return image_bytes, safe_metadata


def default_transport(
    *,
    api_url: str,
    api_key: str,
    request_payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-svodki-image-preview/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:4000]
        raise ImageGenerationError(
            f"Images API HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ImageGenerationError(f"Images API network error: {exc.reason}") from exc
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImageGenerationError("Images API вернул некорректный JSON") from exc
    if not isinstance(payload, dict):
        raise ImageGenerationError("Images API response должен быть JSON-объектом")
    return payload


def generate_image_artifact(
    *,
    source_dir: Path,
    output_dir: Path,
    request_path: Path,
    config_path: Path,
    api_key: str,
    model: str,
    api_url: str = DEFAULT_API_URL,
    timeout_seconds: int = 900,
    transport: Callable[..., dict[str, Any]] = default_transport,
) -> dict[str, Any]:
    config = load_json(config_path, config_path.as_posix())
    request = load_json(request_path, request_path.as_posix())
    if request.get("enabled") is not True or request.get("mode") != "image_api_preview":
        raise ImageGenerationError("Image request не активен или имеет неверный mode")
    if not api_key:
        raise ImageGenerationError("OPENAI_API_KEY отсутствует")

    target_model = str(config.get("target_model", "")).strip()
    if model != target_model:
        raise ImageGenerationError(
            f"OPENAI_IMAGE_MODEL не совпадает с config: {model!r} != {target_model!r}"
        )
    width = int(config["width"])
    height = int(config["height"])
    size = f"{width}x{height}"
    quality = str(config["quality"])
    output_format = str(config["output_format"])
    artifact_filename = str(config["artifact_filename"])

    copied = safe_copy_source(source_dir, output_dir)
    digest = load_json(output_dir / "digest.json", "digest.json")
    source_manifest = load_json(output_dir / "image-source.json", "image-source.json")
    title = str(digest.get("title", "")).strip()
    prompt = str(digest.get("image_prompt", "")).strip()
    publication_date = str(digest.get("date", "")).strip()
    publish_filename = str(digest.get("cover_filename", "")).strip()
    if publication_date != request.get("publication_date"):
        raise ImageGenerationError("Request publication_date не совпадает с digest.date")
    if not all((title, prompt, publication_date, publish_filename)):
        raise ImageGenerationError(
            "digest.json должен содержать title, image_prompt, date и cover_filename"
        )

    prompt_sha256 = sha256_bytes(prompt.encode("utf-8"))
    source_manifest_sha256 = sha256_file(output_dir / "image-source.json")
    request_id = str(request.get("request_id", "")).strip()
    api_request = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "background": "opaque",
    }

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    response_payload = transport(
        api_url=api_url,
        api_key=api_key,
        request_payload=api_request,
        timeout_seconds=timeout_seconds,
    )
    image_bytes, safe_response = parse_response_payload(response_payload)
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    cover_path = output_dir / artifact_filename
    temporary_cover = cover_path.with_suffix(cover_path.suffix + ".tmp")
    temporary_cover.write_bytes(image_bytes)
    temporary_cover.replace(cover_path)
    cover_sha256 = sha256_bytes(image_bytes)

    image_request = {
        "status": "ok",
        "mode": "image_api_preview",
        "request_id": request_id,
        "target_model": target_model,
        "requested_size": size,
        "quality": quality,
        "output_format": output_format,
        "background": "opaque",
        "publication_date": publication_date,
        "title": title,
        "prompt_sha256": prompt_sha256,
        "artifact_filename": artifact_filename,
        "publish_filename": publish_filename,
        "source": request.get("source"),
        "source_manifest_sha256": source_manifest_sha256,
        "editorial_request_id": source_manifest.get("editorial_request_id"),
        "network_used": True,
        "openai_used": True,
        "retry_count": 0,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    image_manifest = {
        "status": "ok",
        "mode": "image_api_preview",
        "request_id": request_id,
        "source": "openai_images_api",
        "endpoint": "/v1/images/generations",
        "artifact_filename": artifact_filename,
        "publish_filename": publish_filename,
        "format": output_format,
        "width": width,
        "height": height,
        "bytes": len(image_bytes),
        "sha256": cover_sha256,
        "prompt_sha256": prompt_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "network_used": True,
        "openai_used": True,
        "visual_semantics_validated": False,
        "rendered_title_validated": False,
        "retry_count": 0,
        "created_at": finished_at,
    }
    image_response = {
        "status": "ok",
        "request_id": request_id,
        "model": model,
        "endpoint": "/v1/images/generations",
        "request": {
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": "opaque",
            "n": 1,
            "prompt_sha256": prompt_sha256,
        },
        "response": safe_response,
        "cover_sha256": cover_sha256,
        "cover_bytes": len(image_bytes),
        "base64_stored": False,
        "copied_source_files": copied,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    write_json(output_dir / "image-request.json", image_request)
    write_json(output_dir / "image-manifest.json", image_manifest)
    write_json(output_dir / "image-api-response.json", image_response)
    return {
        "status": "ok",
        "request_id": request_id,
        "output_dir": str(output_dir),
        "cover": str(cover_path),
        "cover_sha256": cover_sha256,
        "bytes": len(image_bytes),
        "size": size,
        "retry_count": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", default=os.environ.get("OPENAI_IMAGE_MODEL", ""))
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    output_dir = args.output_dir.resolve()
    try:
        result = generate_image_artifact(
            source_dir=args.source_dir.resolve(),
            output_dir=output_dir,
            request_path=args.request.resolve(),
            config_path=args.config.resolve(),
            api_key=api_key,
            model=args.model,
            api_url=args.api_url,
            timeout_seconds=args.timeout_seconds,
        )
        print("Image API preview: ok")
        print(f"Request ID: {result['request_id']}")
        print(f"Cover: {result['cover']}")
        print(f"PNG: {result['size']}, {result['bytes']} bytes")
        print("API calls: 1; retries: 0")
        return 0
    except Exception as exc:
        error = {
            "status": "error",
            "stage": "image_api_preview",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "api_key_stored": False,
            "failed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            write_json(output_dir / "image-api-error.json", error)
        except OSError:
            pass
        print(f"Image API preview failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
