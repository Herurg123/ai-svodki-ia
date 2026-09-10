"""Read-only evidence of a release in a local copy of the origin/main history.

This proves repository publication at a named commit, not FTP delivery. No fetch,
network, worktree reads, or writes are performed by this module.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from source_value_identity import nonempty, valid_url


class PageEvidence(HTMLParser):
    """Visible h3 story blocks, ending at the next heading or content boundary."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    HIDDEN = {"script", "style", "template", "noscript", "nav", "footer", "aside", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.blocks: list[dict[str, Any]] = []
        self.active: dict[str, Any] | None = None
        self.in_heading = False

    def handle_data(self, data):
        if self.active is not None and self.in_heading and not (self.stack and self.stack[-1][1]):
            self.active["headline"].append(data)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent_hidden = bool(self.stack and self.stack[-1][1])
        hidden = parent_hidden or tag in self.HIDDEN or "hidden" in attrs or str(attrs.get("aria-hidden", "")).lower() == "true"
        hidden = hidden or bool(re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", attrs.get("style") or "", re.I))
        if not parent_hidden and tag in {"nav", "footer", "aside"}:
            self.active = None
            self.in_heading = False
        if tag not in self.VOID:
            self.stack.append((tag, hidden))
        if hidden:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.active = None
            self.in_heading = False
            if tag == "h3":
                self.active = {"headline": [], "links": set()}
                self.blocks.append(self.active)
                self.in_heading = True
        if tag == "a" and self.active is not None and valid_url(attrs.get("href")):
            self.active["links"].add(attrs["href"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        hidden = bool(self.stack and self.stack[-1][1])
        if not hidden and tag == "h3":
            self.in_heading = False
        if not hidden and tag in {"body", "article", "section"}:
            self.active = None
            self.in_heading = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def verify_page(post: bytes, stories: Any) -> None:
    page = PageEvidence()
    page.feed(post.decode("utf-8"))
    page.close()
    if not isinstance(stories, list) or not stories or len(page.blocks) != len(stories):
        raise ValueError("committed page must contain exactly the nonempty ordered story list")
    for story, block in zip(stories, page.blocks):
        headline = story.get("headline") if isinstance(story, dict) else None
        sources = story.get("sources") if isinstance(story, dict) else None
        if not nonempty(headline) or not isinstance(sources, list) or not sources or any(not isinstance(s, dict) or not valid_url(s.get("url")) for s in sources):
            raise ValueError("committed story headline or source evidence is malformed")
        urls = [s["url"] for s in sources]
        # Same existing public Meta footnote convention as artifact validation.
        visible_headline = re.sub(r"(?<!\w)Meta\*(?![\w*])", "Meta", " ".join("".join(block["headline"]).split()))
        if (len(urls) != len(set(urls)) or " ".join(headline.split()) != visible_headline
                or not set(urls).issubset(block["links"])):
            raise ValueError("committed story block does not confirm its own exact headline and source URLs")


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError("required committed publication evidence is unavailable")
    return result.stdout


def load_publication(repo: Path, commit: str, publication_date: str) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("publication commit must be a full lowercase commit SHA")
    day = date.fromisoformat(publication_date).isoformat()
    if day != publication_date:
        raise ValueError("publication date must be YYYY-MM-DD")
    # A branch draft must not become proof merely because it has these files.
    git(repo, "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
    post_path = f"posts/{day}/index.html"
    post = git(repo, "show", f"{commit}:{post_path}")
    if not post.strip():
        raise ValueError("committed publication page is empty")
    base = f"automation/content/{day}"
    raw = {key: git(repo, "show", f"{commit}:{base}/{name}") for key, name in [
        ("pulse", "source-pulse.json"), ("candidates", "candidates.json"),
        ("editorial", "editorial-output.json"), ("stories", "stories.json")
    ]}
    bundle = {key: json.loads(value) for key, value in raw.items() if key != "pulse"}
    verify_page(post, bundle["stories"])
    proof = {
        "scope": "repository_publication_on_origin_main",
        "commit": commit, "main_ref": "refs/remotes/origin/main",
        "main_ref_commit": git(repo, "rev-parse", "refs/remotes/origin/main").decode().strip(),
        "publication_date": day, "post_path": post_path,
        "post_sha256": hashlib.sha256(post).hexdigest(),
        "input_sha256": {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        "ftp_delivery": "unknown",
        "page_story_check": "Every ordered visible h3 block matches its exact story headline and all its source URLs. Hidden, navigation and neighboring blocks cannot supply evidence.",
        "limitation": "Establishes repository page/artifact state, not remote delivery or independent factual verification.",
    }
    return raw["pulse"], bundle, proof
