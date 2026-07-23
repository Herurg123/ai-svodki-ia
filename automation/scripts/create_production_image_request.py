from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--publication-date", required=True)
    p.add_argument("--request-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    digest_path = args.source_dir / "digest.json"
    digest = json.loads(digest_path.read_text(encoding="utf-8"))
    if digest.get("status") != "ok":
        raise SystemExit("Digest status must be ok")
    if digest.get("date") != args.publication_date:
        raise SystemExit("Digest date does not match image request date")
    if not str(digest.get("image_prompt", "")).strip():
        raise SystemExit("Digest image_prompt is empty")

    payload = {
        "enabled": True,
        "mode": "image_api_preview",
        "source": args.source_dir.as_posix(),
        "publication_date": args.publication_date,
        "request_id": args.request_id,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Runtime image request written: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
