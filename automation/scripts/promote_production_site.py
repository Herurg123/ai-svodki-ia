from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from production_daily_common import (
    assert_inside, parse_rss, read_json, safe_replace_tree, tree_digest, write_json
)

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--candidate-posts", type=Path, required=True)
    p.add_argument("--live-posts", type=Path, required=True)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--content-root", type=Path, required=True)
    p.add_argument("--publication-date", required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    repo = Path.cwd().resolve()
    config = read_json(args.config)
    candidate = args.candidate_posts.resolve()
    live = args.live_posts.resolve()
    source = args.source_dir.resolve()
    content_root = args.content_root.resolve()

    assert_inside(candidate, repo / "automation" / "preview", "candidate-posts")
    if live != (repo / "posts").resolve():
        raise RuntimeError("live-posts must be repository posts/")
    assert_inside(source, repo / "automation" / "preview", "source-dir")
    if content_root != (repo / str(config["content_root"])).resolve():
        raise RuntimeError("content-root does not match config")

    live_rss = parse_rss(live / "rss.xml")
    candidate_rss = parse_rss(candidate / "rss.xml")
    existing_links = {row["link"] for row in live_rss["items"]}
    candidate_links = {row["link"] for row in candidate_rss["items"]}
    missing = sorted(existing_links - candidate_links)
    if missing:
        raise RuntimeError(f"Candidate RSS lost existing links: {missing}")

    legacy_prefix = str(config["legacy_prefix"])
    legacy_live = {x for x in existing_links if x.startswith(legacy_prefix)}
    legacy_candidate = {x for x in candidate_links if x.startswith(legacy_prefix)}
    if legacy_live != legacy_candidate:
        raise RuntimeError("Candidate RSS changed legacy dzen-test links")

    expected_new = (
        f"{str(config['site_base_url']).rstrip('/')}/{args.publication_date}/"
    )
    if expected_new not in candidate_links:
        raise RuntimeError(f"Candidate RSS does not contain {expected_new}")

    candidate_text = (candidate / "rss.xml").read_text(encoding="utf-8").casefold()
    if "blogspot.com" in candidate_text or "blogger.googleusercontent.com" in candidate_text:
        raise RuntimeError("Candidate RSS contains Blogger dependency")

    before = tree_digest(live)
    content_target = content_root / args.publication_date
    if content_target.exists():
        raise RuntimeError(f"Content target already exists: {content_target}")

    report = {
        "status": "ok",
        "dry_run": args.dry_run,
        "publication_date": args.publication_date,
        "live_before_sha256": before,
        "candidate_sha256": tree_digest(candidate),
        "existing_items": len(existing_links),
        "candidate_items": len(candidate_links),
        "legacy_items": len(legacy_candidate),
        "new_link": expected_new,
    }

    if not args.dry_run:
        safe_replace_tree(candidate, live)
        content_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, content_target)
        report["live_after_sha256"] = tree_digest(live)
        report["content_sha256"] = tree_digest(content_target)
    else:
        report["live_after_sha256"] = tree_digest(live)
        if report["live_after_sha256"] != before:
            raise RuntimeError("Dry-run modified live posts")

    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
