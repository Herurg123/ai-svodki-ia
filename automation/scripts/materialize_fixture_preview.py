from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import zlib
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from editorial_policy import read_policy, validate_article_policy, validate_stories

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "digest-preview"
    / "2026-07-11"
    / "digest.json"
)
PREVIEW_ROOT = ROOT / "automation" / "preview"
EDITORIAL_CONFIG_PATH = ROOT / "automation" / "config" / "editorial.json"


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Развернуть тестовый digest в preview-каталог без внешних API."
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="Путь к fixture digest.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Каталог назначения. По умолчанию automation/preview/YYYY-MM-DD.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Fixture не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в fixture: {exc}") from exc


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def assert_safe_output(path: Path) -> None:
    resolved = path.resolve()
    preview_root = PREVIEW_ROOT.resolve()
    if preview_root not in resolved.parents:
        raise RuntimeError(
            "Fixture разрешено создавать только внутри automation/preview/."
        )
    if resolved == (ROOT / "posts").resolve():
        raise RuntimeError("Рабочий каталог posts/ запрещён для fixture.")


def validate_digest(digest: dict[str, Any], stories: list[dict[str, Any]]) -> None:
    required = {
        "status",
        "error_message",
        "date",
        "slug",
        "title",
        "description",
        "published_at",
        "author",
        "cover_filename",
        "article_html",
        "image_prompt",
        "topics",
        "sources",
        "short_digest",
        "editorial_notes",
    }
    missing = sorted(required.difference(digest))
    if missing:
        raise RuntimeError("В fixture отсутствуют поля: " + ", ".join(missing))

    if digest["status"] != "ok" or digest["error_message"] is not None:
        raise RuntimeError("Fixture должен иметь status=ok и error_message=null.")

    try:
        parsed_date = date.fromisoformat(str(digest["date"]))
    except ValueError as exc:
        raise RuntimeError("Некорректная дата fixture.") from exc

    if digest["slug"] != digest["date"]:
        raise RuntimeError("slug должен совпадать с date.")

    expected_title = f"ИИ-Сводка на {parsed_date.day} июля {parsed_date.year}"
    if digest["title"] != expected_title:
        raise RuntimeError(f"Неожиданный заголовок fixture: {digest['title']!r}")

    expected_cover = f"ai-svodka-{digest['date']}.png"
    if digest["cover_filename"] != expected_cover:
        raise RuntimeError(f"cover_filename должен быть {expected_cover!r}.")

    article_html = str(digest["article_html"]).strip()
    lowered = article_html.lower()
    for forbidden in ("<h1", "<img", "<html", "<head", "<body", "<script"):
        if forbidden in lowered:
            raise RuntimeError(f"article_html содержит запрещённый фрагмент {forbidden}.")

    sources = digest["sources"]
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("sources должен быть непустым массивом.")

    source_urls = {str(source.get("url", "")).strip() for source in sources}
    if "" in source_urls:
        raise RuntimeError("В sources есть пустой URL.")

    collector = LinkCollector()
    collector.feed(article_html)
    article_urls = set(collector.links)
    dzen_url = str(read_policy(EDITORIAL_CONFIG_PATH)["dzen"]["url"])
    article_urls.discard(dzen_url)
    if source_urls != article_urls:
        raise RuntimeError(
            "Ссылки article_html не совпадают с sources: "
            f"article={sorted(article_urls)}, sources={sorted(source_urls)}"
        )


    policy = read_policy(EDITORIAL_CONFIG_PATH)
    selected_candidates = [
        {
            "id": str(story.get("candidate_id", "")),
            "archive_status": (
                "update" if story.get("status") == "update" else "none"
            ),
            "geography": str(story.get("geography", "world")),
            "organization": str(story.get("organization", "")),
            "primary_source": (
                story.get("sources", [{}])[0]
                if isinstance(story.get("sources"), list) and story.get("sources")
                else {}
            ),
        }
        for story in stories
    ]
    story_errors = validate_stories(stories, selected_candidates)
    policy_errors, _warnings, _analysis = validate_article_policy(
        article_html,
        selected_candidates,
        bool(digest["short_digest"]),
        policy,
    )
    combined = story_errors + policy_errors
    if combined:
        raise RuntimeError("Fixture нарушает editorial policy:\n- " + "\n- ".join(combined))


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    body = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def build_placeholder_png(width: int = 1280, height: int = 720) -> bytes:
    rows: list[bytes] = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            base = 18 + int(34 * y / max(height - 1, 1))
            pulse = 36 if (x // 96 + y // 72) % 2 == 0 else 0
            line = 70 if x % 160 in {0, 1} or y % 120 in {0, 1} else 0
            red = min(255, base + pulse // 4)
            green = min(255, base + 18 + pulse + line // 2)
            blue = min(255, base + 42 + pulse + line)
            row.extend((red, green, blue))
        rows.append(b"\x00" + bytes(row))

    raw = b"".join(rows)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        signature
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + png_chunk(b"IEND", b"")
    )


def main() -> int:
    args = parse_args()
    fixture_path = args.fixture
    if not fixture_path.is_absolute():
        fixture_path = (ROOT / fixture_path).resolve()

    try:
        digest = read_json(fixture_path)
        if not isinstance(digest, dict):
            raise RuntimeError("Корень fixture должен быть JSON-объектом.")
        stories_path = fixture_path.with_name("stories.json")
        stories = read_json(stories_path)
        if not isinstance(stories, list) or not stories:
            raise RuntimeError("Fixture stories.json должен содержать непустой массив.")
        validate_digest(digest, stories)

        output_dir = args.output_dir
        if output_dir is None:
            output_dir = PREVIEW_ROOT / digest["date"]
        elif not output_dir.is_absolute():
            output_dir = ROOT / output_dir
        output_dir = output_dir.resolve()
        assert_safe_output(output_dir)

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            key: digest[key]
            for key in (
                "status",
                "error_message",
                "date",
                "slug",
                "title",
                "description",
                "published_at",
                "author",
                "cover_filename",
                "topics",
                "short_digest",
                "editorial_notes",
            )
        }
        digest_text = pretty_json(digest)
        run_info = {
            "status": "ok",
            "mode": "fixture",
            "fixture": str(fixture_path.relative_to(ROOT)),
            "publication_date": digest["date"],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "digest_sha256": hashlib.sha256(
                digest_text.encode("utf-8")
            ).hexdigest(),
            "network_used": False,
            "openai_used": False,
        }

        atomic_write(output_dir / "digest.json", digest_text)
        atomic_write(output_dir / "meta.json", pretty_json(meta))
        atomic_write(
            output_dir / "article.html",
            str(digest["article_html"]).strip() + "\n",
        )
        atomic_write(
            output_dir / "image-prompt.txt",
            str(digest["image_prompt"]).strip() + "\n",
        )
        atomic_write(output_dir / "sources.json", pretty_json(digest["sources"]))
        atomic_write(output_dir / "stories.json", pretty_json(stories))
        atomic_write(output_dir / "run-info.json", pretty_json(run_info))
        (output_dir / "cover.png").write_bytes(build_placeholder_png())

        print(f"Fixture preview создан: {output_dir.relative_to(ROOT)}")
        print("Сетевые запросы: нет")
        print("OpenAI API: нет")
        return 0
    except Exception as exc:
        print(f"Fixture preview failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
