
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Callable

from production_daily_common import parse_rss, read_json, write_json

OpenUrl = Callable[..., Any]


def _http_status(
    url: str,
    *,
    opener: OpenUrl,
    timeout: int,
) -> int:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-svodki-release-continuity/1.0",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            return int(response.status)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ) as exc:
        raise RuntimeError(
            f"Живой адрес предыдущего выпуска недоступен: {url}; "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def verify(
    *,
    config: dict[str, Any],
    rss: dict[str, Any],
    posts_root: Path,
    publication_date: str,
    opener: OpenUrl = urllib.request.urlopen,
    timeout: int = 20,
) -> dict[str, Any]:
    target = date.fromisoformat(publication_date)
    latest = rss["latest_item"]
    previous_date = date.fromisoformat(str(latest["date"]))

    if previous_date >= target:
        raise RuntimeError(
            "Предыдущий опубликованный выпуск должен быть старше нового: "
            f"previous={previous_date}, target={target}."
        )

    site_base = str(config["site_base_url"]).rstrip("/")
    expected_article_url = f"{site_base}/{previous_date.isoformat()}/"
    expected_image_url = (
        f"{site_base}/images/ai-svodka-{previous_date.isoformat()}.png"
    )
    if str(latest["link"]) != expected_article_url:
        raise RuntimeError(
            "Последний RSS item указывает не на канонический выпуск: "
            f"ожидалось {expected_article_url}, получено {latest['link']}."
        )

    article_path = posts_root / previous_date.isoformat() / "index.html"
    image_path = (
        posts_root
        / "images"
        / f"ai-svodka-{previous_date.isoformat()}.png"
    )
    missing = [
        str(path)
        for path in (article_path, image_path)
        if not path.is_file()
    ]
    if missing:
        raise RuntimeError(
            "Последний выпуск указан в RSS, но в GitHub отсутствуют "
            "канонические файлы: " + ", ".join(missing)
        )

    live_checks_enabled = bool(
        config.get("verify_previous_release_on_live_site", True)
    )
    live_statuses: dict[str, int | str] = {
        "article": "not_checked",
        "image": "not_checked",
    }
    if live_checks_enabled:
        article_status = _http_status(
            expected_article_url,
            opener=opener,
            timeout=timeout,
        )
        image_status = _http_status(
            expected_image_url,
            opener=opener,
            timeout=timeout,
        )
        live_statuses = {
            "article": article_status,
            "image": image_status,
        }
        if article_status != 200 or image_status != 200:
            raise RuntimeError(
                "Предыдущий выпуск не подтверждён на живом сайте: "
                f"article={article_status}, image={image_status}."
            )

    return {
        "status": "ok",
        "publication_date": target.isoformat(),
        "previous_published_date": previous_date.isoformat(),
        "missed_calendar_days": max(
            (target - previous_date).days - 1,
            0,
        ),
        "repository": {
            "article": str(article_path),
            "image": str(image_path),
            "verified": True,
        },
        "live": {
            "article_url": expected_article_url,
            "image_url": expected_image_url,
            "statuses": live_statuses,
            "verified": live_checks_enabled,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rss", type=Path, required=True)
    parser.add_argument("--posts-root", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        report = verify(
            config=read_json(args.config),
            rss=parse_rss(args.rss),
            posts_root=args.posts_root,
            publication_date=args.publication_date,
            timeout=args.timeout,
        )
    except Exception as exc:
        report = {
            "status": "error",
            "publication_date": args.publication_date,
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_json(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
