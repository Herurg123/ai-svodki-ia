from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_object(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Cannot read {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} contains invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    digest = load_object(args.source_dir / "digest.json", "digest.json")
    if digest.get("status") != "ok":
        raise SystemExit("Digest status must be ok")
    if digest.get("date") != args.publication_date:
        raise SystemExit("Digest date does not match image request date")
    if not str(digest.get("image_prompt", "")).strip():
        raise SystemExit("Digest image_prompt is empty")

    manifest_name = "artifact-validation.json"
    manifest = load_object(args.source_dir / manifest_name, manifest_name)
    if manifest.get("status") != "ok":
        raise SystemExit(f"{manifest_name} status must be ok")

    payload = {
        "enabled": True,
        "mode": "image_api_preview",
        "source": args.source_dir.as_posix(),
        "source_manifest": manifest_name,
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
