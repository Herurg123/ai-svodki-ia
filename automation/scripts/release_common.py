from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def resolve_from_root(value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def relative_to_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def assert_inside(path: Path, parent: Path, label: str) -> None:
    resolved = path.resolve()
    allowed = parent.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise RuntimeError(f"{label} должен находиться внутри {allowed}.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    excluded = exclude or set()
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        if path.is_symlink():
            raise RuntimeError(f"Символические ссылки запрещены: {path}")
        result[relative] = sha256_file(path)
    return result


def tree_digest(root: Path, *, exclude: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    for relative, file_hash in file_manifest(root, exclude=exclude).items():
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def parse_iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"Некорректная дата-время: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"Дата-время не содержит часовой пояс: {value!r}")
    return parsed


def current_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_value(name: str, default: str = "unknown") -> str:
    return os.environ.get(name, default)
