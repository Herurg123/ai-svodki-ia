from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_images(source: Path, target: Path, *, dry_run: bool) -> dict:
    files = sorted(source.glob("ai-svodka-*.png"))
    if len(files) < 10:
        raise ValueError(f"Expected at least 10 legacy images, got {len(files)}")

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
                different_existing.append({
                    "name": src.name,
                    "legacy_sha256": source_hash,
                    "production_sha256": target_hash,
                })
            continue

        copied.append(src.name)
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    return {
        "status": "ok",
        "dry_run": dry_run,
        "source_images": len(files),
        "would_copy" if dry_run else "copied": copied,
        "already_present": existing,
        "different_existing": different_existing,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    repo = Path.cwd().resolve()
    source = args.source.resolve()
    target = args.target.resolve()
    expected_source = (repo / "posts" / "dzen-test" / "images").resolve()
    expected_target = (repo / "posts" / "images").resolve()
    if source != expected_source or target != expected_target:
        raise SystemExit("Legacy image paths must be posts/dzen-test/images -> posts/images")
    if not source.is_dir():
        raise SystemExit(f"Legacy image source is missing: {source}")

    try:
        report = stage_images(source, target, dry_run=args.dry_run)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
