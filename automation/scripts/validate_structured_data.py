from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SCRIPT_ID = "ai-svodki-structured-data"


class ScriptExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.parts: list[str] = []
        self.payloads: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        self.capture = (
            tag == "script"
            and values.get("type") == "application/ld+json"
            and values.get("id") == SCRIPT_ID
        )
        if self.capture:
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.capture:
            self.payloads.append("".join(self.parts))
            self.capture = False


def load_graph(path: Path) -> dict[str, Any]:
    parser = ScriptExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    if len(parser.payloads) != 1:
        raise RuntimeError(
            f"{path}: expected exactly one generated structured-data block"
        )
    value = json.loads(parser.payloads[0])
    if value.get("@context") != "https://schema.org":
        raise RuntimeError(f"{path}: wrong @context")
    if not isinstance(value.get("@graph"), list):
        raise RuntimeError(f"{path}: @graph missing")
    return value


def by_type(graph: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [
        node for node in graph["@graph"]
        if node.get("@type") == kind
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--posts-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    digest = json.loads(
        (args.source_dir / "digest.json").read_text(encoding="utf-8")
    )
    sources = json.loads(
        (args.source_dir / "sources.json").read_text(encoding="utf-8")
    )
    publication_date = str(digest["date"])
    article_path = args.posts_root / publication_date / "index.html"
    index_path = args.posts_root / "index.html"
    rss_path = args.posts_root / "rss.xml"
    errors: list[str] = []

    try:
        article_graph = load_graph(article_path)
        index_graph = load_graph(index_path)
    except Exception as exc:
        errors.append(str(exc))
        article_graph = {"@graph": []}
        index_graph = {"@graph": []}

    articles = by_type(article_graph, "BlogPosting")
    if len(articles) != 1:
        errors.append("article page must contain exactly one BlogPosting")
    else:
        article = articles[0]
        required = [
            "@id", "headline", "description", "datePublished", "dateModified",
            "author", "publisher", "image", "mainEntityOfPage", "isPartOf",
            "wordCount", "inLanguage", "articleBody", "citation"
        ]
        for key in required:
            if key not in article:
                errors.append(f"BlogPosting missing {key}")
        if article.get("headline") != digest.get("title"):
            errors.append("BlogPosting headline differs from digest title")
        if article.get("description") != digest.get("description"):
            errors.append("BlogPosting description differs from digest")
        expected_urls = {
            str(source.get("url"))
            for source in sources
            if str(source.get("url", "")).startswith(("https://", "http://"))
        }
        actual_urls = set(article.get("citation", []))
        if actual_urls != expected_urls:
            errors.append("BlogPosting citations differ from sources.json")
        if (
            not isinstance(article.get("wordCount"), int)
            or article.get("wordCount", 0) < 100
        ):
            errors.append("BlogPosting wordCount is implausible")

    expected_ids = {
        "Person": "https://rybalka.one/#person",
        "WebSite": "https://rybalka.one/#website",
        "Blog": "https://rybalka.one/posts/#blog",
        "Organization": "https://it-expertise.ru/#organization",
    }
    for kind, expected_id in expected_ids.items():
        nodes = by_type(article_graph, kind)
        if len(nodes) != 1:
            errors.append(f"article graph must contain exactly one {kind}")
        elif nodes[0].get("@id") != expected_id:
            errors.append(f"{kind} has wrong @id")

    for kind in ("WebPage", "ImageObject", "BreadcrumbList"):
        if len(by_type(article_graph, kind)) != 1:
            errors.append(f"article graph must contain exactly one {kind}")

    if len(by_type(index_graph, "Blog")) != 1:
        errors.append("index graph must contain Blog")
    if len(by_type(index_graph, "CollectionPage")) != 1:
        errors.append("index graph must contain CollectionPage")
    lists = by_type(index_graph, "ItemList")
    if len(lists) != 1 or lists[0].get("numberOfItems", 0) < 1:
        errors.append("index graph must contain a non-empty ItemList")

    if 'application/ld+json' in rss_path.read_text(encoding="utf-8"):
        errors.append("RSS must not contain JSON-LD scripts")

    for path in (article_path, index_path):
        html = path.read_text(encoding="utf-8")
        if 'rel="canonical"' not in html:
            errors.append(f"{path}: canonical missing")
        if 'name="robots"' not in html:
            errors.append(f"{path}: robots meta missing")
        if 'type="application/rss+xml"' not in html:
            errors.append(f"{path}: RSS discovery link missing")

    report = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "article": str(article_path),
        "index": str(index_path),
        "rss_unchanged_by_schema": True,
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
