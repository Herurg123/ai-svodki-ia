from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

SCRIPT_ID = "ai-svodki-structured-data"


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return " ".join(self.parts)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def plain_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


def unique_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = " ".join(str(raw).split()).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def ensure_head_value(html: str, tag: str, marker: str) -> str:
    if marker in html:
        return html
    if "</head>" not in html:
        raise RuntimeError("HTML head closing tag is missing")
    return html.replace("</head>", f"  {tag}\n</head>", 1)


def remove_old_block(html: str) -> str:
    pattern = re.compile(
        rf'\s*<script\s+id="{re.escape(SCRIPT_ID)}"\s+'
        rf'type="application/ld\+json">.*?</script>\s*',
        re.S | re.I,
    )
    return pattern.sub("\n", html)


def json_script(graph: dict[str, Any]) -> str:
    payload = json.dumps(graph, ensure_ascii=False, indent=2)
    payload = payload.replace("</", "<\\/")
    return (
        f'<script id="{SCRIPT_ID}" type="application/ld+json">\n'
        f'{payload}\n'
        f'</script>'
    )


def image_dimensions(image_path: Path) -> tuple[int, int]:
    data = image_path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError(f"Unsupported or invalid PNG: {image_path}")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def common_nodes(config: dict[str, Any]) -> list[dict[str, Any]]:
    organization = {
        "@type": "Organization",
        "@id": config["organization_id"],
        "name": config["organization_name"],
        "url": config["organization_url"],
    }
    person = {
        "@type": "Person",
        "@id": config["person_id"],
        "name": config["person_name"],
        "url": config["person_url"],
        "image": config["person_image_url"],
        "jobTitle": config["person_job_title"],
        "description": config["person_description"],
        "worksFor": {"@id": config["organization_id"]},
        "sameAs": config["person_same_as"],
        "knowsAbout": config["person_knows_about"],
    }
    website = {
        "@type": "WebSite",
        "@id": config["website_id"],
        "url": config["site_url"],
        "name": config["website_name"],
        "inLanguage": config["default_language"],
        "publisher": {"@id": config["person_id"]},
    }
    blog = {
        "@type": "Blog",
        "@id": config["blog_id"],
        "url": config["blog_url"],
        "name": config["blog_name"],
        "description": config["blog_description"],
        "inLanguage": config["default_language"],
        "isPartOf": {"@id": config["website_id"]},
        "author": {"@id": config["person_id"]},
        "publisher": {"@id": config["person_id"]},
        "sameAs": config["feed_url"],
    }
    return [organization, person, website, blog]


def article_graph(
    *,
    config: dict[str, Any],
    digest: dict[str, Any],
    stories: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    article_url: str,
    image_url: str,
    image_width: int,
    image_height: int,
) -> dict[str, Any]:
    article_id = article_url + "#blogposting"
    webpage_id = article_url + "#webpage"
    image_id = image_url + "#image"
    breadcrumb_id = article_url + "#breadcrumb"

    body = plain_text(str(digest.get("article_html", "")))
    topics = unique_text([str(x) for x in digest.get("topics", [])])
    keywords: list[str] = list(topics)
    mentions: list[dict[str, Any]] = []
    seen_organizations: set[str] = set()

    for story in stories:
        keywords.extend(str(x) for x in story.get("keywords", []))
        organization = " ".join(str(story.get("organization", "")).split())
        key = organization.casefold()
        if organization and key not in seen_organizations:
            seen_organizations.add(key)
            mentions.append({"@type": "Organization", "name": organization})

    citations = unique_text([
        str(source.get("url", ""))
        for source in sources
        if str(source.get("url", "")).startswith(("https://", "http://"))
    ])

    published = str(digest["published_at"])
    modified = str(digest.get("modified_at") or published)
    publication_year = str(digest["date"])[:4]

    image = {
        "@type": "ImageObject",
        "@id": image_id,
        "url": image_url,
        "contentUrl": image_url,
        "width": image_width,
        "height": image_height,
        "caption": digest["title"],
        "inLanguage": config["default_language"],
        "representativeOfPage": True,
    }
    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": breadcrumb_id,
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": config["website_name"],
                "item": config["site_url"],
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": config["blog_name"],
                "item": config["blog_url"],
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": digest["title"],
                "item": article_url,
            },
        ],
    }
    webpage = {
        "@type": "WebPage",
        "@id": webpage_id,
        "url": article_url,
        "name": digest["title"],
        "description": digest["description"],
        "isPartOf": {"@id": config["website_id"]},
        "breadcrumb": {"@id": breadcrumb_id},
        "primaryImageOfPage": {"@id": image_id},
        "mainEntity": {"@id": article_id},
        "inLanguage": config["default_language"],
        "datePublished": published,
        "dateModified": modified,
    }
    article: dict[str, Any] = {
        "@type": "BlogPosting",
        "@id": article_id,
        "url": article_url,
        "mainEntityOfPage": {"@id": webpage_id},
        "headline": digest["title"],
        "description": digest["description"],
        "abstract": digest["description"],
        "datePublished": published,
        "dateModified": modified,
        "author": {"@id": config["person_id"]},
        "publisher": {"@id": config["person_id"]},
        "copyrightHolder": {"@id": config["person_id"]},
        "copyrightYear": int(publication_year),
        "image": {"@id": image_id},
        "thumbnailUrl": image_url,
        "isPartOf": {"@id": config["blog_id"]},
        "articleSection": config["default_article_section"],
        "genre": config["genre"],
        "keywords": unique_text(keywords),
        "about": [{"@type": "Thing", "name": value} for value in topics],
        "wordCount": len(re.findall(r"\b[\wЁёА-Яа-я-]+\b", body, flags=re.UNICODE)),
        "inLanguage": config["default_language"],
        "isAccessibleForFree": True,
        "conditionsOfAccess": "Бесплатно",
        "creativeWorkStatus": "Published",
        "encodingFormat": "text/html",
    }
    if config.get("include_article_body", True):
        article["articleBody"] = body
    if config.get("include_citations", True):
        article["citation"] = citations
    if config.get("include_mentions", True):
        article["mentions"] = mentions

    return {
        "@context": config["context"],
        "@graph": common_nodes(config) + [image, breadcrumb, webpage, article],
    }


def index_graph(
    *,
    config: dict[str, Any],
    rss_path: Path,
) -> dict[str, Any]:
    root = ET.parse(rss_path).getroot()
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel missing")
    entries = []
    for position, item in enumerate(channel.findall("item"), start=1):
        link = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        if link and title:
            entries.append({
                "@type": "ListItem",
                "position": position,
                "url": link,
                "name": title,
            })

    collection = {
        "@type": "CollectionPage",
        "@id": config["blog_url"] + "#webpage",
        "url": config["blog_url"],
        "name": config["blog_name"],
        "description": config["blog_description"],
        "isPartOf": {"@id": config["website_id"]},
        "mainEntity": {"@id": config["blog_id"]},
        "inLanguage": config["default_language"],
    }
    listing = {
        "@type": "ItemList",
        "@id": config["blog_url"] + "#itemlist",
        "itemListElement": entries,
        "numberOfItems": len(entries),
    }
    return {
        "@context": config["context"],
        "@graph": common_nodes(config) + [collection, listing],
    }


def inject(path: Path, graph: dict[str, Any], canonical: str, feed_url: str) -> None:
    html = remove_old_block(path.read_text(encoding="utf-8"))
    html = ensure_head_value(
        html,
        f'<link rel="canonical" href="{canonical}">',
        'rel="canonical"',
    )
    html = ensure_head_value(
        html,
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        'name="robots"',
    )
    html = ensure_head_value(
        html,
        (
            f'<link rel="alternate" type="application/rss+xml" '
            f'title="ИИ-Сводки" href="{feed_url}">'
        ),
        'type="application/rss+xml"',
    )
    html = html.replace("</head>", "  " + json_script(graph) + "\n</head>", 1)
    path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--posts-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    config = read_json(args.config)
    digest = read_json(args.source_dir / "digest.json")
    stories = read_json(args.source_dir / "stories.json")
    sources = read_json(args.source_dir / "sources.json")
    if digest.get("status") != "ok":
        raise RuntimeError("Digest status must be ok")

    publication_date = str(digest["date"])
    article_path = args.posts_root / publication_date / "index.html"
    image_path = args.posts_root / "images" / str(digest["cover_filename"])
    index_path = args.posts_root / "index.html"
    rss_path = args.posts_root / "rss.xml"

    for required in (article_path, image_path, index_path, rss_path):
        if not required.exists():
            raise RuntimeError(f"Required file missing: {required}")

    article_url = config["blog_url"].rstrip("/") + f"/{publication_date}/"
    image_url = (
        config["blog_url"].rstrip("/")
        + "/images/"
        + str(digest["cover_filename"])
    )
    width, height = image_dimensions(image_path)

    inject(
        article_path,
        article_graph(
            config=config,
            digest=digest,
            stories=stories,
            sources=sources,
            article_url=article_url,
            image_url=image_url,
            image_width=width,
            image_height=height,
        ),
        article_url,
        config["feed_url"],
    )
    inject(
        index_path,
        index_graph(config=config, rss_path=rss_path),
        config["blog_url"],
        config["feed_url"],
    )

    report = {
        "status": "ok",
        "article": str(article_path),
        "article_url": article_url,
        "index": str(index_path),
        "blog_url": config["blog_url"],
        "image_url": image_url,
        "image_width": width,
        "image_height": height,
        "citations": len(sources),
        "stories": len(stories),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
