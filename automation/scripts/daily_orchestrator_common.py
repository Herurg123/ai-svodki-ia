from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def current_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise RuntimeError(f"Каталог не найден: {root}")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Символические ссылки запрещены: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, file_hash in file_manifest(root).items():
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"JSON-файл не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def resolve_from_root(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def relative_to_root(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def assert_inside(path: Path, parent: Path, label: str) -> None:
    resolved = path.resolve()
    parent_resolved = parent.resolve()
    try:
        resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise RuntimeError(f"{label} должен находиться внутри {parent_resolved}: {resolved}") from exc


def require_safe_relative(value: str, label: str) -> None:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"{label} содержит небезопасный путь: {value!r}")


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != 1:
        raise RuntimeError("daily orchestrator config: schema_version должен быть 1.")
    if config.get("enabled") is not True:
        raise RuntimeError("daily orchestrator должен быть enabled=true.")
    if config.get("mode") != "recorded_fixture_replay":
        raise RuntimeError("Разрешён только mode=recorded_fixture_replay.")
    if config.get("preview_branch") != "automation-prep":
        raise RuntimeError("Replay разрешён только для automation-prep.")

    for field in (
        "output_root",
        "replay_source",
        "research_fixture",
        "editorial_fixture",
        "release_fixture",
    ):
        value = config.get(field)
        if not isinstance(value, str):
            raise RuntimeError(f"{field} должен быть строкой.")
        require_safe_relative(value, field)

    output_root = resolve_from_root(config["output_root"])
    assert_inside(output_root, ROOT / "automation" / "preview", "output_root")
    assert_inside(
        resolve_from_root(config["replay_source"]),
        ROOT / "automation" / "fixtures" / "daily-orchestrator",
        "replay_source",
    )
    assert_inside(
        resolve_from_root(config["research_fixture"]),
        ROOT / "automation" / "fixtures" / "research",
        "research_fixture",
    )
    assert_inside(
        resolve_from_root(config["editorial_fixture"]),
        ROOT / "automation" / "fixtures" / "editorial",
        "editorial_fixture",
    )
    assert_inside(
        resolve_from_root(config["release_fixture"]),
        ROOT / "automation" / "fixtures" / "release",
        "release_fixture",
    )

    safety = config.get("safety")
    if not isinstance(safety, dict):
        raise RuntimeError("safety должен быть объектом.")
    forbidden = [name for name, value in safety.items() if value is not False]
    required = {
        "allow_network",
        "allow_openai",
        "allow_ftp",
        "allow_repository_write",
        "allow_schedule",
        "allow_production_posts",
        "allow_request_file_changes",
    }
    missing = sorted(required - set(safety))
    if missing:
        raise RuntimeError(f"В safety отсутствуют поля: {missing}")
    if forbidden:
        raise RuntimeError(f"Replay safety-флаги должны быть false: {forbidden}")

    expected = config.get("expected")
    if not isinstance(expected, dict):
        raise RuntimeError("expected должен быть объектом.")
    for field in ("editorial_request_id", "image_request_id", "image_model", "cover_sha256"):
        if not isinstance(expected.get(field), str) or not expected[field]:
            raise RuntimeError(f"expected.{field} должен быть непустой строкой.")
    for field in ("research_candidates", "selected_stories"):
        if not isinstance(expected.get(field), int) or expected[field] < 1:
            raise RuntimeError(f"expected.{field} должен быть положительным целым.")


def compare_manifest(actual: dict[str, str], expected: dict[str, Any], label: str) -> None:
    normalized = {str(name): str(value) for name, value in expected.items()}
    if actual == normalized:
        return
    missing = sorted(set(normalized) - set(actual))
    extra = sorted(set(actual) - set(normalized))
    changed = sorted(
        key for key in set(actual).intersection(normalized) if actual[key] != normalized[key]
    )
    raise RuntimeError(
        f"{label}: fixture manifest не совпадает; "
        f"missing={missing}, extra={extra}, changed={changed}"
    )
