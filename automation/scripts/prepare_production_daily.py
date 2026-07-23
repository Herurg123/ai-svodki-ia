from __future__ import annotations
import argparse
from pathlib import Path
from production_daily_common import parse_rss, read_json, runtime_context, write_json

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rss", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--publication-date")
    parser.add_argument("--now")
    args = parser.parse_args()

    context = runtime_context(
        config=read_json(args.config),
        rss=parse_rss(args.rss),
        now_iso=args.now,
        publication_date_override=args.publication_date,
    )
    write_json(args.output, context)
    if args.github_output:
        args.github_output.parent.mkdir(parents=True, exist_ok=True)
        with args.github_output.open("a", encoding="utf-8") as stream:
            for key in (
                "publication_date",
                "previous_date",
                "target_url",
                "digest_request_id",
                "image_request_id",
            ):
                stream.write(f"{key}={context[key]}\n")
    print(f"Production runtime prepared for {context['publication_date']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
