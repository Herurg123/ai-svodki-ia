from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from release_common import file_manifest, sha256_file, tree_digest

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or not value or value in {".", ".."} or ".." in path.parts:
        raise RuntimeError(f"Небезопасный относительный путь: {value!r}")


def validate_manifest(files: dict[str, str]) -> None:
    if not isinstance(files, dict):
        raise RuntimeError("Файловый manifest должен быть JSON-объектом.")
    for relative, digest in files.items():
        validate_relative_path(str(relative))
        if not SHA256_RE.fullmatch(str(digest)):
            raise RuntimeError(f"Некорректный SHA-256 для {relative!r}: {digest!r}")


def diff_manifests(before: dict[str, str], after: dict[str, str]) -> list[dict[str, Any]]:
    validate_manifest(before)
    validate_manifest(after)
    operations: list[dict[str, Any]] = []
    for relative in sorted(set(before) | set(after)):
        old_hash = before.get(relative)
        new_hash = after.get(relative)
        if old_hash is None:
            action = "add"
        elif new_hash is None:
            action = "delete"
        elif old_hash != new_hash:
            action = "update"
        else:
            continue
        operations.append(
            {
                "action": action,
                "path": relative,
                "before_sha256": old_hash,
                "after_sha256": new_hash,
            }
        )
    return operations


def operation_summary(operations: list[dict[str, Any]]) -> dict[str, int]:
    result = {"add": 0, "update": 0, "delete": 0, "total": len(operations)}
    for operation in operations:
        action = str(operation.get("action"))
        if action not in {"add", "update", "delete"}:
            raise RuntimeError(f"Неизвестная операция: {action!r}")
        result[action] += 1
    return result


def clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Каталог-источник не существует: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    for item in source.rglob("*"):
        if item.is_symlink():
            raise RuntimeError(f"Символические ссылки запрещены: {item}")
    shutil.copytree(source, destination)


def apply_operations(
    working_tree: Path,
    source_tree: Path,
    operations: list[dict[str, Any]],
) -> None:
    for operation in operations:
        action = str(operation["action"])
        relative = str(operation["path"])
        validate_relative_path(relative)
        target = working_tree / relative
        source = source_tree / relative
        if action in {"add", "update"}:
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f"Нет безопасного исходного файла для {action}: {source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            expected = operation.get("after_sha256")
            if expected and sha256_file(target) != expected:
                raise RuntimeError(f"SHA-256 после {action} не совпал: {relative}")
        elif action == "delete":
            if target.exists():
                if not target.is_file() or target.is_symlink():
                    raise RuntimeError(f"Удалять разрешено только обычные файлы: {target}")
                target.unlink()
        else:
            raise RuntimeError(f"Неизвестная операция: {action!r}")

    directories = sorted(
        (path for path in working_tree.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def describe_tree(root: Path) -> dict[str, Any]:
    files = file_manifest(root)
    return {
        "path": str(root),
        "files": files,
        "file_count": len(files),
        "tree_sha256": tree_digest(root),
    }
