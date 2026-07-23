from __future__ import annotations
import argparse, json, re
from pathlib import Path
import xml.etree.ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rss", type=Path, required=True)
    p.add_argument("--feed-url", required=True)
    p.add_argument("--site-link", required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()

    text = args.rss.read_text(encoding="utf-8")
    errors = []

    # Preserve CDATA by editing the text, not reserializing the whole document.
    atom_pattern = re.compile(
        r'<atom:link\b[^>]*\brel="self"[^>]*/>',
        re.IGNORECASE,
    )
    replacement = (
        f'<atom:link href="{args.feed_url}" rel="self" '
        'type="application/rss+xml" />'
    )
    if atom_pattern.search(text):
        text = atom_pattern.sub(replacement, text, count=1)
    else:
        text = text.replace("<channel>", "<channel>" + replacement, 1)

    # Ensure every item is explicitly marked as an article and immediate/native.
    def normalize_item(match: re.Match[str]) -> str:
        block = match.group(0)
        if "<category>Статья</category>" not in block:
            block = block.replace(
                "<description>",
                "<category>Статья</category><description>",
                1,
            )
        if "<category>native-yes</category>" not in block:
            block = block.replace(
                "<description>",
                "<category>native-yes</category><description>",
                1,
            )
        return block

    text = re.sub(r"<item>.*?</item>", normalize_item, text, flags=re.S)
    args.rss.write_text(text, encoding="utf-8")

    try:
        root = ET.parse(args.rss).getroot()
    except ET.ParseError as exc:
        errors.append(f"XML invalid after normalization: {exc}")
        root = None

    item_count = 0
    if root is not None:
        channel = root.find("channel")
        if channel is None:
            errors.append("channel missing")
        else:
            atom = channel.find(f"{{{ATOM_NS}}}link")
            self_url = atom.get("href", "") if atom is not None else ""
            if self_url != args.feed_url:
                errors.append(f"wrong self URL: {self_url}")
            item_count = len(channel.findall("item"))
            for item in channel.findall("item"):
                categories = {
                    (node.text or "").strip()
                    for node in item.findall("category")
                }
                if "Статья" not in categories:
                    errors.append("item missing category Статья")
                if "native-yes" not in categories:
                    errors.append("item missing category native-yes")
                link = (item.findtext("link") or "").strip()
                if not link.startswith(args.site_link.rstrip("/") + "/"):
                    errors.append(f"external item link: {link}")

    lowered = text.casefold()
    for forbidden in ("blogspot.com", "blogger.googleusercontent.com"):
        if forbidden in lowered:
            errors.append(f"forbidden external dependency: {forbidden}")

    report = {
        "status": "ok" if not errors else "error",
        "rss": str(args.rss),
        "items": item_count,
        "errors": errors,
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
