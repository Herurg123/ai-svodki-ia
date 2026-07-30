from __future__ import annotations

import argparse
import json
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
import xml.etree.ElementTree as ET

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
IMAGE_NS = "http://www.google.com/schemas/sitemap-image/1.1"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace("", SITEMAP_NS)
ET.register_namespace("image", IMAGE_NS)


def text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def build_sitemap(
    *,
    rss: Path,
    posts_root: Path,
    output: Path,
    base_url: str = "https://rybalka.one/posts/",
    reference_date: date | None = None,
) -> dict[str, str | int]:
    if posts_root.is_symlink() or not posts_root.is_dir():
        raise RuntimeError(f"Posts root must be a regular directory: {posts_root}")

    rss_root = ET.parse(rss).getroot()
    channel = rss_root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel missing")

    base = base_url.rstrip("/") + "/"
    entries: list[dict[str, str]] = [
        {
            "loc": base,
            "lastmod": (reference_date or date.today()).isoformat(),
            "changefreq": "daily",
            "priority": "0.9",
            "image": "",
        }
    ]

    seen = {base}
    for item in channel.findall("item"):
        link = text(item.find("link"))
        pub_raw = text(item.find("pubDate"))
        enclosure = item.find("enclosure")
        image_url = (
            enclosure.get("url", "").strip()
            if enclosure is not None
            else ""
        )
        if not link.startswith(base):
            raise RuntimeError(f"External item link cannot enter sitemap: {link}")
        if link in seen:
            continue
        seen.add(link)
        lastmod = parsedate_to_datetime(pub_raw).date().isoformat()
        entries.append({
            "loc": link,
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": "0.8",
            "image": image_url if image_url.startswith(base) else "",
        })

    urlset = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for entry in entries:
        url = ET.SubElement(urlset, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(url, f"{{{SITEMAP_NS}}}loc").text = entry["loc"]
        ET.SubElement(url, f"{{{SITEMAP_NS}}}lastmod").text = entry["lastmod"]
        ET.SubElement(url, f"{{{SITEMAP_NS}}}changefreq").text = entry["changefreq"]
        ET.SubElement(url, f"{{{SITEMAP_NS}}}priority").text = entry["priority"]
        if entry["image"]:
            image = ET.SubElement(url, f"{{{IMAGE_NS}}}image")
            ET.SubElement(image, f"{{{IMAGE_NS}}}loc").text = entry["image"]

    output.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)

    report = {
        "status": "ok",
        "urls": len(entries),
        "articles": len(entries) - 1,
        "output": str(output),
        "base_url": base,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rss", type=Path, required=True)
    parser.add_argument("--posts-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--base-url",
        default="https://rybalka.one/posts/",
    )
    parser.add_argument(
        "--reference-date",
        help="Optional deterministic YYYY-MM-DD date for the index lastmod.",
    )
    args = parser.parse_args()

    reference_date = (
        date.fromisoformat(args.reference_date)
        if args.reference_date
        else None
    )
    report = build_sitemap(
        rss=args.rss,
        posts_root=args.posts_root,
        output=args.output,
        base_url=args.base_url,
        reference_date=reference_date,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
