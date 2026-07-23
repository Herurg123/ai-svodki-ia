#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORBIDDEN = {
    "cover.png",
    "image-request.json",
    "image-manifest.json",
    "image-api-response.json",
    "cover-validation.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} должен содержать JSON-объект")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    source = args.source_dir
    manifest_path = source / "image-source.json"

    if not source.is_dir():
        errors.append(f"Не найден recovery source: {source}")
        manifest: dict[str, Any] = {}
    elif not manifest_path.is_file():
        errors.append("Отсутствует image-source.json")
        manifest = {}
    else:
        try:
            manifest = load_json(manifest_path)
        except Exception as exc:
            errors.append(f"Некорректный image-source.json: {exc}")
            manifest = {}

    if manifest:
        if manifest.get("status") != "ok":
            errors.append("image-source.status должен быть ok")
        if manifest.get("source_type") != "recovered_validated_editorial_artifact":
            errors.append("Неверный source_type recovery artifact")
        if manifest.get("publication_date") != args.publication_date:
            errors.append("publication_date не совпадает")
        if manifest.get("editorial_artifact_validation_status") != "ok":
            errors.append("Редакционный artifact не валиден")

        files = manifest.get("files")
        if not isinstance(files, dict):
            errors.append("image-source.files должен быть объектом")
            files = {}

        actual = {
            path.name
            for path in source.iterdir()
            if path.is_file() and path.name != "image-source.json"
        }
        expected = set(files)
        if actual != expected:
            errors.append(
                f"Набор файлов не совпадает: missing={sorted(expected-actual)}, "
                f"extra={sorted(actual-expected)}"
            )

        for name, expected_hash in files.items():
            path = source / name
            if not path.is_file() or path.is_symlink():
                errors.append(f"Не найден обычный файл: {name}")
                continue
            actual_hash = sha256_file(path)
            if actual_hash != expected_hash:
                errors.append(f"SHA-256 не совпадает для {name}")

        for name in FORBIDDEN:
            if (source / name).exists():
                errors.append(f"Recovery source не должен содержать {name}")

        try:
            digest = load_json(source / "digest.json")
            run_info = load_json(source / "run-info.json")
            validation = load_json(source / "artifact-validation.json")
            recovery = load_json(source / "recovery-normalization.json")
            if digest.get("status") != "ok" or digest.get("date") != args.publication_date:
                errors.append("digest.json не соответствует дате или status")
            if run_info.get("status") != "ok":
                errors.append("run-info.status должен быть ok")
            if run_info.get("request_id") != manifest.get("editorial_request_id"):
                errors.append("editorial_request_id не совпадает с run-info")
            if validation.get("status") != "ok" or validation.get("errors"):
                errors.append("artifact-validation.json не имеет status=ok")
            if recovery.get("status") != "ok":
                errors.append("recovery-normalization.status должен быть ok")
            for field in ("content_changed", "facts_changed", "sources_changed"):
                if recovery.get(field) is not False:
                    errors.append(f"recovery-normalization.{field} должен быть false")
        except Exception as exc:
            errors.append(f"Не удалось проверить lineage recovery artifact: {exc}")

    report = {
        "validator": "recovered-editorial-source",
        "status": "ok" if not errors else "error",
        "source_dir": source.as_posix(),
        "publication_date": args.publication_date,
        "errors": errors,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
