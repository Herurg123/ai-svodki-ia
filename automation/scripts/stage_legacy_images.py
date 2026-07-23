from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    repo = Path.cwd().resolve()
    source = args.source.resolve()
    target = args.target.resolve()
    expected_source = (repo / 'posts' / 'dzen-test' / 'images').resolve()
    expected_target = (repo / 'posts' / 'images').resolve()
    if source != expected_source or target != expected_target:
        raise SystemExit('Legacy image paths must be posts/dzen-test/images -> posts/images')
    if not source.is_dir():
        raise SystemExit(f'Legacy image source is missing: {source}')

    files = sorted(source.glob('ai-svodka-*.png'))
    if len(files) < 10:
        raise SystemExit(f'Expected at least 10 legacy images, got {len(files)}')

    copied, existing = [], []
    for src in files:
        dst = target / src.name
        if dst.exists():
            if sha256(src) != sha256(dst):
                raise SystemExit(f'Canonical image differs from legacy source: {dst}')
            existing.append(src.name)
            continue
        copied.append(src.name)
        if not args.dry_run:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    report = {
        'status': 'ok',
        'dry_run': args.dry_run,
        'source_images': len(files),
        'would_copy' if args.dry_run else 'copied': copied,
        'already_present': existing,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
