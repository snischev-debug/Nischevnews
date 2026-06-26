"""Сбор новостей из RSS-источников: парсинг, фильтр по свежести, дедуп."""
import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from time import mktime

import feedparser
import yaml

import config

log = logging.getLogger("fetcher")


@dataclass
class Item:
    title: str
    summary: str
    url: str
    source_name: str
    theme: str
    origin: str          # foreign | ru
    published: str       # ISO-строка


def _load_sources():
    with open(config.SOURCES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


def _parse_one(src, lookback_hours: int) -> list[Item]:
    """Синхронный парсинг одного фида (вызывается в потоке)."""
    items: list[Item] = []
    try:
        feed = feedparser.parse(src["url"])
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось разобрать %s: %s", src["name"], e)
        return items

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    for e in feed.entries:
        # дата публикации
        ts = e.get("published_parsed") or e.get("updated_parsed")
        if ts:
            published = datetime.fromtimestamp(mktime(ts), tz=timezone.utc)
        else:
            published = datetime.now(timezone.utc)
        if published < cutoff:
            continue

        summary = (e.get("summary") or e.get("description") or "").strip()
        # грубая чистка html
        for tag in ("<p>", "</p>", "<br>", "<br/>", "<b>", "</b>"):
            summary = summary.replace(tag, " ")
        summary = " ".join(summary.split())[:600]

        items.append(Item(
            title=(e.get("title") or "").strip(),
            summary=summary,
            url=e.get("link") or "",
            source_name=src["name"],
            theme=src.get("theme", "other"),
            origin=src.get("origin", "ru"),
            published=published.isoformat(),
        ))
    return items


async def fetch_all(lookback_hours: int | None = None) -> list[dict]:
    """Тянем все источники параллельно, чистим, дедуплицируем по заголовку/ссылке."""
    if lookback_hours is None:
        lookback_hours = config.LOOKBACK_HOURS
    sources = _load_sources()
    results = await asyncio.gather(
        *[asyncio.to_thread(_parse_one, s, lookback_hours) for s in sources],
        return_exceptions=True,
    )

    all_items: list[Item] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        all_items.extend(r)

    # дедуп
    seen_url, seen_title, deduped = set(), set(), []
    for it in all_items:
        key_t = it.title.lower().strip()
        if it.url in seen_url or key_t in seen_title:
            continue
        seen_url.add(it.url)
        seen_title.add(key_t)
        deduped.append(it)

    # свежие сверху, обрезаем до лимита для модели
    deduped.sort(key=lambda x: x.published, reverse=True)
    log.info("Собрано %d свежих материалов (после дедупа)", len(deduped))
    return [asdict(it) for it in deduped[: config.MAX_ITEMS_TO_LLM]]
