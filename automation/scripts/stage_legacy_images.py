from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_images(source: Path, target: Path, *, dry_run: bool) -> dict:
    files = sorted(source.glob("ai-svodka-*.png"))

    copied: list[str] = []
    existing: list[str] = []
    different_existing: list[dict[str, str]] = []

    for src in files:
        dst = target / src.name
        if dst.exists():
            source_hash = sha256(src)
            target_hash = sha256(dst)
            existing.append(src.name)
            if source_hash != target_hash:
                # Production images are canonical. A differing legacy image is
                # recorded for audit, but must never overwrite production.
                different_existing.append(
                    {
                        "name": src.name,
                        "legacy_sha256": source_hash,
                        "production_sha256": target_hash,
                    }
                )
            continue

        copied.append(src.name)
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    return {
        "status": "ok",
        "blocking": False,
        "dry_run": dry_run,
        "source_images": len(files),
        "would_copy" if dry_run else "copied": copied,
        "already_present": existing,
        "different_existing": different_existing,
        "warnings": [],
    }


def stage_images_best_effort(source: Path, target: Path, *, dry_run: bool) -> dict:
    """Stage legacy assets without making a migration helper a release gate.

    The canonical site build and its validators remain responsible for deciding
    whether publication is safe. Legacy staging only fills historical assets
    that may still be useful to the compatibility build.
    """
    if not source.is_dir():
        return {
            "status": "warning",
            "blocking": False,
            "dry_run": dry_run,
            "source_images": 0,
            "would_copy" if dry_run else "copied": [],
            "already_present": [],
            "different_existing": [],
            "warnings": [f"Legacy image source is missing: {source}"],
        }

    try:
        return stage_images(source, target, dry_run=dry_run)
    except OSError as exc:
        return {
            "status": "warning",
            "blocking": False,
            "dry_run": dry_run,
            "source_images": None,
            "would_copy" if dry_run else "copied": [],
            "already_present": [],
            "different_existing": [],
            "warnings": [f"Legacy image staging skipped: {type(exc).__name__}: {exc}"],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    source = args.source.resolve()
    target = args.target.resolve()
    expected_source = (repo / "posts" / "dzen-test" / "images").resolve()
    expected_target = (repo / "posts" / "images").resolve()
    if source != expected_source or target != expected_target:
        raise SystemExit("Legacy image paths must be posts/dzen-test/images -> posts/images")

    report = stage_images_best_effort(source, target, dry_run=args.dry_run)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok":
        print(
            "Legacy staging produced a warning; canonical site build/validation "
            "will decide whether publication can continue."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
