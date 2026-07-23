from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sitemap", type=Path, required=True)
    parser.add_argument("--rss", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    sitemap_root = ET.parse(args.sitemap).getroot()
    rss_root = ET.parse(args.rss).getroot()

    sitemap_urls = {
        (node.text or "").strip()
        for node in sitemap_root.findall("s:url/s:loc", NS)
    }
    rss_urls = {
        (node.text or "").strip()
        for node in rss_root.findall("./channel/item/link")
    }

    expected_index = "https://rybalka.one/posts/"
    if expected_index not in sitemap_urls:
        errors.append("posts index is missing from sitemap")
    missing = sorted(rss_urls - sitemap_urls)
    if missing:
        errors.append(f"RSS links missing from sitemap: {missing}")
    external = sorted(
        value for value in sitemap_urls
        if not value.startswith("https://rybalka.one/posts/")
    )
    if external:
        errors.append(f"External sitemap URLs: {external}")

    report = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "sitemap_urls": len(sitemap_urls),
        "rss_urls": len(rss_urls),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
