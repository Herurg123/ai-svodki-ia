"""Bounded first-party fallback evidence; no model calls or guessed dates."""
from __future__ import annotations

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree

from source_freshness_v1 import PublicationEvidence

OPENAI_NEWS_FEED = 'https://openai.com/news/rss.xml'


def _openai_article(url: str) -> str | None:
    p = urlsplit(url)
    if (p.scheme != 'https' or p.netloc != 'openai.com' or p.query or p.fragment
            or not re.fullmatch(r'/index/[a-z0-9][a-z0-9-]*/?', p.path)):
        return None
    return p.path.rstrip('/')


class _OpenAIHeroDate(HTMLParser):
    """Read only the visible article metadata region, never arbitrary body dates."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.paragraph = False
        self.text = []
        self.dates = []

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            if self.depth:
                self.depth += 1
            elif dict(attrs).get('data-article-hero-copy-region') == 'meta':
                self.depth = 1
        if self.depth and tag == 'p':
            self.paragraph = True
            self.text = []

    def handle_data(self, data):
        if self.depth and self.paragraph:
            self.text.append(data)

    def handle_endtag(self, tag):
        if self.depth and tag == 'p' and self.paragraph:
            self.paragraph = False
            try:
                self.dates.append(datetime.strptime(''.join(self.text).strip(), '%B %d, %Y').date())
            except ValueError:
                pass
        if self.depth and tag == 'div':
            self.depth -= 1


def openai_feed_evidence(body: str, requested: str, final: str, fetcher):
    article = _openai_article(requested)
    if article is None or _openai_article(final) != article:
        return None
    parser = _OpenAIHeroDate()
    parser.feed(body)
    if len(parser.dates) != 1:
        return None
    raw, feed_final, status = fetcher(OPENAI_NEWS_FEED)
    if status != 200 or feed_final != OPENAI_NEWS_FEED:
        return None
    # Standard-library XML parsing cannot fetch external entities; a malformed
    # or ambiguous feed fails closed, and transport retains its existing cap.
    feed = ElementTree.fromstring(raw)
    matching = [item for item in feed.findall('./channel/item')
                if _openai_article(item.findtext('link') or '') == article]
    if len(matching) != 1:
        return None
    value = matching[0].findtext('pubDate')
    if not value:
        return None
    try:
        at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None or at.date() != parser.dates[0]:
        return None
    return PublicationEvidence(value, at.date(), at, 'datetime',
                               'openai-rss:pubDate:' + OPENAI_NEWS_FEED, 1)


def _same_yandex_article(requested: str, final: str) -> bool:
    a, b = urlsplit(requested), urlsplit(final)
    if (a.scheme != 'https' or b.scheme != 'https' or a.hostname != b.hostname
            or not a.hostname or not (a.hostname == 'yandex.ru' or a.hostname.endswith('.yandex.ru'))):
        return False
    if a.username or b.username or a.port not in (None, 443) or b.port not in (None, 443):
        return False
    # Do not borrow dates from another same-day release or a redirect to an index.
    return a.path.rstrip('/') == b.path.rstrip('/') and a.query == b.query


def github_release_api_url(url: str) -> str | None:
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'github.com' or p.query or p.fragment:
        return None
    match = re.fullmatch(r'/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/releases/tag/([^/]+)', p.path)
    if not match:
        return None
    owner, repo, encoded_tag = match.groups()
    tag = unquote(encoded_tag)
    if not tag or '/' in tag or '\\' in tag or tag in {'.', '..'}:
        return None
    return f'https://api.github.com/repos/{owner}/{repo}/releases/tags/{quote(tag, safe="")}'


def first_party_evidence(body: str, requested_url: str, final_url: str, fetcher):
    """Called only after successful HTML fetch with no generic publication date.

    Yandex reuses the proven Pulse parser on the same exact article. GitHub
    permits one derived public Releases API request, through the existing safe
    fetcher, and binds every accepted field to the cited repository/tag URL.
    """
    if _same_yandex_article(requested_url, final_url):
        # Lazy import preserves source_freshness / Pulse compatibility imports.
        from source_pulse_supplement_v13 import extract_yandex_publication_evidence
        evidence = extract_yandex_publication_evidence(body, final_url)
        if evidence is not None:
            return evidence
    if _openai_article(requested_url) is not None:
        return openai_feed_evidence(body, requested_url, final_url, fetcher)
    endpoint = github_release_api_url(requested_url)
    if endpoint is None or requested_url != final_url:
        return None
    raw, api_final_url, status = fetcher(endpoint)
    if status != 200 or api_final_url != endpoint:
        return None
    release = json.loads(raw)
    if not isinstance(release, dict):
        return None
    tag = unquote(urlsplit(requested_url).path.rsplit('/', 1)[1])
    if (release.get('html_url') != requested_url or release.get('tag_name') != tag
            or release.get('draft') is not False):
        return None
    value = release.get('published_at')
    if not isinstance(value, str):
        return None
    try:
        at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if at.tzinfo is None:
        return None
    return PublicationEvidence(value, at.date(), at, 'datetime',
                               'github-releases-api:published_at:' + endpoint, 1)
