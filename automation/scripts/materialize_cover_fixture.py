#!/usr/bin/env python3
"""Create a deterministic, offline PNG cover fixture and its manifests.

The script never calls OpenAI or any other network service. It replaces only the
cover inside an isolated digest artifact directory and writes image-request.json
and image-manifest.json beside it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "automation" / "config" / "image.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cover", type=Path, default=None)
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный JSON: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    body = chunk_type + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def build_fixture_png(width: int, height: int) -> bytes:
    """Build an RGB PNG without text or metadata chunks."""
    if width <= 0 or height <= 0:
        raise ValueError("Размеры PNG должны быть положительными.")

    compressor = zlib.compressobj(level=9)
    compressed_parts: list[bytes] = []
    for y in range(height):
        row = bytearray([0])  # PNG filter type 0
        for x in range(width):
            grid = 42 if x % 192 in {0, 1} or y % 108 in {0, 1} else 0
            diagonal = 34 if (x + 2 * y) % 257 < 3 else 0
            pulse = ((x // 96) ^ (y // 72)) & 1
            red = min(255, 16 + y * 38 // max(height - 1, 1) + diagonal)
            green = min(255, 34 + x * 44 // max(width - 1, 1) + grid + pulse * 16)
            blue = min(255, 72 + (x + y) * 56 // max(width + height - 2, 1) + grid)
            row.extend((red, green, blue))
        compressed_parts.append(compressor.compress(bytes(row)))
    compressed_parts.append(compressor.flush())

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", b"".join(compressed_parts))
        + png_chunk(b"IEND", b"")
    )


def resolve(path: Path, base: Path) -> Path:
    return path if path.is_absolute() else (base / path).resolve()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    args = parse_args()
    try:
        artifact_dir = resolve(args.artifact_dir, ROOT)
        config_path = resolve(args.config, ROOT)
        config = read_json(config_path)
        digest = read_json(artifact_dir / "digest.json")
        if not isinstance(config, dict) or not isinstance(digest, dict):
            raise RuntimeError("Config и digest должны быть JSON-объектами.")

        width = int(config["width"])
        height = int(config["height"])
        artifact_filename = str(config["artifact_filename"])
        cover_path = (
            resolve(args.cover, ROOT)
            if args.cover is not None
            else artifact_dir / artifact_filename
        )
        request_path = (
            resolve(args.request, ROOT)
            if args.request is not None
            else artifact_dir / "image-request.json"
        )
        manifest_path = (
            resolve(args.manifest, ROOT)
            if args.manifest is not None
            else artifact_dir / "image-manifest.json"
        )

        title = str(digest.get("title", "")).strip()
        prompt = str(digest.get("image_prompt", "")).strip()
        publication_date = str(digest.get("date", "")).strip()
        publish_filename = str(digest.get("cover_filename", "")).strip()
        if not all((title, prompt, publication_date, publish_filename)):
            raise RuntimeError(
                "digest.json должен содержать title, image_prompt, date и cover_filename."
            )

        png = build_fixture_png(width, height)
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(png)
        prompt_sha256 = sha256_bytes(prompt.encode("utf-8"))
        cover_sha256 = sha256_bytes(png)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        request = {
            "status": "ok",
            "mode": "offline_fixture",
            "target_model": config["target_model"],
            "requested_size": f"{width}x{height}",
            "quality": config["quality"],
            "output_format": config["output_format"],
            "publication_date": publication_date,
            "title": title,
            "prompt_sha256": prompt_sha256,
            "artifact_filename": artifact_filename,
            "publish_filename": publish_filename,
            "network_used": False,
            "openai_used": False,
            "created_at": created_at,
        }
        manifest = {
            "status": "ok",
            "mode": "offline_fixture",
            "source": "deterministic_python_fixture",
            "artifact_filename": artifact_filename,
            "publish_filename": publish_filename,
            "format": "png",
            "width": width,
            "height": height,
            "bytes": len(png),
            "sha256": cover_sha256,
            "prompt_sha256": prompt_sha256,
            "network_used": False,
            "openai_used": False,
            "visual_semantics_validated": False,
            "rendered_title_validated": False,
            "created_at": created_at,
        }
        write_json(request_path, request)
        write_json(manifest_path, manifest)

        print(f"Offline cover fixture: {cover_path}")
        print(f"PNG: {width}x{height}, {len(png)} bytes")
        print("Network used: false")
        print("OpenAI used: false")
        print("Visual semantics validated: false")
        return 0
    except Exception as exc:
        print(f"Cover fixture materialization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
