#!/usr/bin/env python3
"""Validate an image artifact, its request metadata and PNG container.

This validator is offline and standard-library only. It validates the technical
contract and prompt metadata. It deliberately does not claim to verify visual
semantics or OCR the rendered title.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "automation" / "config" / "image.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TEXT_CHUNKS = {"tEXt", "zTXt", "iTXt"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args()


def resolve(path: Path, base: Path) -> Path:
    return path if path.is_absolute() else (base / path).resolve()


def load_json(path: Path, report: dict[str, Any], code: str) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        add_error(report, code, f"Не найден файл: {path}")
    except UnicodeDecodeError as exc:
        add_error(report, code, f"JSON должен быть UTF-8: {exc}")
    except json.JSONDecodeError as exc:
        add_error(report, code, f"Некорректный JSON: {exc}")
    return None


def add_error(report: dict[str, Any], code: str, message: str) -> None:
    report["errors"].append({"code": code, "message": message})


def add_warning(report: dict[str, Any], code: str, message: str) -> None:
    report["warnings"].append({"code": code, "message": message})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_png(path: Path, report: dict[str, Any]) -> dict[str, Any] | None:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        add_error(report, "cover_read", f"Не удалось прочитать PNG: {exc}")
        return None
    if not payload.startswith(PNG_SIGNATURE):
        add_error(report, "png_signature", "Файл не имеет сигнатуру PNG.")
        return None

    position = len(PNG_SIGNATURE)
    chunks: list[str] = []
    text_chunks: list[str] = []
    width = height = bit_depth = color_type = None
    idat_count = 0
    iend_seen = False

    while position < len(payload):
        if position + 12 > len(payload):
            add_error(report, "png_truncated", "PNG обрывается внутри заголовка chunk.")
            return None
        length = struct.unpack(">I", payload[position : position + 4])[0]
        chunk_type_bytes = payload[position + 4 : position + 8]
        end = position + 12 + length
        if end > len(payload):
            add_error(report, "png_truncated", "PNG обрывается внутри данных chunk.")
            return None
        try:
            chunk_type = chunk_type_bytes.decode("ascii")
        except UnicodeDecodeError:
            add_error(report, "png_chunk_type", "Тип PNG chunk не является ASCII.")
            return None
        chunk_data = payload[position + 8 : position + 8 + length]
        expected_crc = struct.unpack(">I", payload[position + 8 + length : end])[0]
        actual_crc = zlib.crc32(chunk_type_bytes + chunk_data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            add_error(report, "png_crc", f"Неверный CRC у chunk {chunk_type}.")

        chunks.append(chunk_type)
        if chunk_type in TEXT_CHUNKS:
            text_chunks.append(chunk_type)
        if chunk_type == "IHDR":
            if len(chunks) != 1:
                add_error(report, "png_ihdr_order", "IHDR должен быть первым chunk.")
            if length != 13:
                add_error(report, "png_ihdr_length", "IHDR должен иметь длину 13 байт.")
            else:
                (
                    width,
                    height,
                    bit_depth,
                    color_type,
                    compression,
                    filter_method,
                    interlace,
                ) = struct.unpack(">IIBBBBB", chunk_data)
                if compression != 0 or filter_method != 0:
                    add_error(
                        report,
                        "png_methods",
                        "PNG использует неподдерживаемый compression/filter method.",
                    )
                if interlace != 0:
                    add_error(report, "png_interlace", "Interlaced PNG не разрешён.")
        elif chunk_type == "IDAT":
            idat_count += 1
        elif chunk_type == "IEND":
            if length != 0:
                add_error(report, "png_iend_length", "IEND должен быть пустым.")
            iend_seen = True
            position = end
            if position != len(payload):
                add_error(report, "png_trailing_bytes", "После IEND найдены лишние байты.")
            break
        position = end

    if chunks.count("IHDR") != 1:
        add_error(report, "png_ihdr_count", "PNG должен содержать ровно один IHDR.")
    if idat_count < 1:
        add_error(report, "png_idat_missing", "PNG не содержит IDAT.")
    if not iend_seen or chunks.count("IEND") != 1:
        add_error(report, "png_iend_count", "PNG должен содержать ровно один IEND.")

    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "chunks": chunks,
        "text_chunks": text_chunks,
    }


def require_equal(
    report: dict[str, Any], code: str, actual: Any, expected: Any, label: str
) -> None:
    if actual != expected:
        add_error(report, code, f"{label}: actual={actual!r}, expected={expected!r}.")


def validate_prompt(
    prompt: str, title: str, config: dict[str, Any], report: dict[str, Any]
) -> str:
    prompt = prompt.strip()
    if not prompt:
        add_error(report, "prompt_missing", "В digest отсутствует image_prompt.")
        return ""
    blocks = [str(value) for value in config.get("required_prompt_blocks", [])]
    positions = [prompt.find(block) for block in blocks]
    for block, position in zip(blocks, positions):
        if position < 0:
            add_error(report, "prompt_block", f"Отсутствует блок «{block}».")
    if all(position >= 0 for position in positions) and positions != sorted(positions):
        add_error(report, "prompt_order", "Блоки image_prompt идут в неверном порядке.")
    if blocks and not prompt.lstrip().startswith(blocks[0]):
        add_error(report, "prompt_prefix", f"Prompt должен начинаться с «{blocks[0]}».")
    if title and title not in prompt:
        add_error(report, "prompt_title", f"В prompt отсутствует точный заголовок: {title}.")

    lowered = prompt.lower()
    for constraint in config.get("required_prompt_constraints", []):
        constraint_text = str(constraint).lower()
        if constraint_text not in lowered:
            add_error(
                report,
                "prompt_constraint",
                f"Отсутствует обязательное ограничение «{constraint}».",
            )
    for constraint in config.get("recommended_prompt_constraints", []):
        constraint_text = str(constraint).lower()
        if constraint_text not in lowered:
            add_warning(
                report,
                "prompt_recommendation",
                f"Отсутствует рекомендуемое ограничение «{constraint}».",
            )
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def validate_contract(artifact_dir: Path, config_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "validator": "cover-contract",
        "status": "error",
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "artifact_dir": str(artifact_dir),
        "errors": [],
        "warnings": [],
        "technical_contract_validated": True,
        "visual_semantics_validated": False,
        "rendered_title_validated": False,
    }
    config = load_json(config_path, report, "config")
    digest = load_json(artifact_dir / "digest.json", report, "digest")
    request = load_json(artifact_dir / "image-request.json", report, "request")
    manifest = load_json(artifact_dir / "image-manifest.json", report, "manifest")
    if not all(isinstance(value, dict) for value in (config, digest, request, manifest)):
        return report
    assert isinstance(config, dict)
    assert isinstance(digest, dict)
    assert isinstance(request, dict)
    assert isinstance(manifest, dict)

    artifact_filename = str(config.get("artifact_filename", "cover.png"))
    cover_path = artifact_dir / artifact_filename
    if not cover_path.is_file():
        add_error(report, "cover_missing", f"Не найден {artifact_filename}.")
        return report

    title = str(digest.get("title", "")).strip()
    publication_date = str(digest.get("date", "")).strip()
    publish_filename = str(digest.get("cover_filename", "")).strip()
    prompt_sha256 = validate_prompt(
        str(digest.get("image_prompt", "")), title, config, report
    )
    png = parse_png(cover_path, report)
    if png is None:
        return report
    report["png"] = png

    width = int(config["width"])
    height = int(config["height"])
    require_equal(report, "png_width", png["width"], width, "Ширина PNG")
    require_equal(report, "png_height", png["height"], height, "Высота PNG")
    if isinstance(png["width"], int) and isinstance(png["height"], int):
        if png["width"] * 9 != png["height"] * 16:
            add_error(report, "png_aspect", "PNG должен иметь точное соотношение 16:9.")
    require_equal(
        report, "png_bit_depth", png["bit_depth"], int(config["bit_depth"]), "Bit depth"
    )
    if png["color_type"] not in config.get("allowed_color_types", []):
        add_error(
            report,
            "png_color_type",
            f"Color type {png['color_type']} не разрешён.",
        )
    if png["bytes"] < int(config["minimum_bytes"]):
        add_error(report, "png_too_small", "PNG меньше установленного минимума.")
    if png["bytes"] > int(config["maximum_bytes"]):
        add_error(report, "png_too_large", "PNG превышает установленный максимум.")
    if config.get("forbid_text_chunks") and png["text_chunks"]:
        add_error(
            report,
            "png_text_chunks",
            f"В PNG запрещены текстовые chunks: {png['text_chunks']}.",
        )

    expected_size = f"{width}x{height}"
    expected_values = {
        "target_model": config["target_model"],
        "requested_size": expected_size,
        "quality": config["quality"],
        "output_format": config["output_format"],
        "publication_date": publication_date,
        "title": title,
        "prompt_sha256": prompt_sha256,
        "artifact_filename": artifact_filename,
        "publish_filename": publish_filename,
    }
    for key, expected in expected_values.items():
        require_equal(report, f"request_{key}", request.get(key), expected, f"request.{key}")

    mode = request.get("mode")
    if mode not in {"offline_fixture", "image_api_preview"}:
        add_error(report, "request_mode", f"Неизвестный image request mode: {mode!r}.")
    require_equal(report, "request_status", request.get("status"), "ok", "request.status")
    if not isinstance(request.get("network_used"), bool) or not isinstance(
        request.get("openai_used"), bool
    ):
        add_error(report, "request_flags", "network_used/openai_used должны быть boolean.")
    elif mode == "offline_fixture" and (
        request["network_used"] or request["openai_used"]
    ):
        add_error(
            report,
            "request_fixture_flags",
            "Offline fixture обязан иметь network_used=false и openai_used=false.",
        )
    elif mode == "image_api_preview" and not (
        request["network_used"] and request["openai_used"]
    ):
        add_error(
            report,
            "request_api_flags",
            "Image API preview обязан фиксировать network_used=true и openai_used=true.",
        )

    manifest_expected = {
        "status": "ok",
        "mode": mode,
        "artifact_filename": artifact_filename,
        "publish_filename": publish_filename,
        "format": config["output_format"],
        "width": width,
        "height": height,
        "bytes": png["bytes"],
        "sha256": png["sha256"],
        "prompt_sha256": prompt_sha256,
        "network_used": request.get("network_used"),
        "openai_used": request.get("openai_used"),
        "visual_semantics_validated": False,
        "rendered_title_validated": False,
    }
    for key, expected in manifest_expected.items():
        require_equal(
            report,
            f"manifest_{key}",
            manifest.get(key),
            expected,
            f"manifest.{key}",
        )

    report["cover"] = str(cover_path)
    report["cover_sha256"] = sha256_file(cover_path)
    report["prompt_sha256"] = prompt_sha256
    report["status"] = "ok" if not report["errors"] else "error"
    return report


def main() -> int:
    args = parse_args()
    artifact_dir = resolve(args.artifact_dir, ROOT)
    config_path = resolve(args.config, ROOT)
    report_path = (
        resolve(args.report, ROOT)
        if args.report is not None
        else artifact_dir / "cover-validation.json"
    )
    report = validate_contract(artifact_dir, config_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Cover validation: {report['status']}")
    print(f"Errors: {len(report['errors'])}; warnings: {len(report['warnings'])}")
    print("Visual semantics validated: false")
    for item in report["errors"]:
        print(f"ERROR {item['code']}: {item['message']}")
    for item in report["warnings"]:
        print(f"WARN {item['code']}: {item['message']}")
    print(f"Report: {report_path}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
