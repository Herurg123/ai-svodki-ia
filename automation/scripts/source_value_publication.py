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


class PageEvidence(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: set[str] = set()
        self.hidden_depth = 0

    def handle_data(self, data):
        if not self.hidden_depth:
            self.text.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden_depth += 1
        if self.hidden_depth:
            return
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.add(href)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.hidden_depth:
            self.hidden_depth -= 1


def verify_page(post: bytes, stories: Any) -> None:
    page = PageEvidence()
    page.feed(post.decode("utf-8"))
    text = " ".join(" ".join(page.text).split())
    if not isinstance(stories, list):
        raise ValueError("committed stories must be a list")
    for story in stories:
        headline = story.get("headline") if isinstance(story, dict) else None
        sources = story.get("sources") if isinstance(story, dict) else None
        urls = {s["url"] for s in sources if isinstance(s, dict) and isinstance(s.get("url"), str)} if isinstance(sources, list) else set()
        if not isinstance(headline, str) or not headline.strip() or " ".join(headline.split()) not in text or not urls.intersection(page.links):
            raise ValueError("committed page does not confirm each story headline and source URL")


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
        "page_story_check": "All story headlines and at least one exact source URL occur in the committed page.",
        "limitation": "Establishes repository page/artifact state, not remote delivery or independent factual verification.",
    }
    return raw["pulse"], bundle, proof
