"""Чтение собственного канала: наши уже опубликованные посты + их статистика.

Зачем: (а) месячный дайджест лучших НАШИХ постов; (б) петля обратной связи —
агент видит, что заходит, и смещает утренний подбор в эту сторону.

Технически нужен Telethon с ПОЛЬЗОВАТЕЛЬСКОЙ сессией (бот историю канала читать не может).
Если ключи не заданы — функции честно сообщают, что не настроено, остальной бот работает.
"""
import logging
from datetime import datetime, timezone, timedelta

import config

log = logging.getLogger("channel_reader")

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    _HAS_TELETHON = True
except ImportError:  # библиотека не установлена
    _HAS_TELETHON = False


def configured() -> bool:
    return bool(_HAS_TELETHON and config.TELETHON_API_ID
               and config.TELETHON_API_HASH and config.TELETHON_SESSION)


def _first_line(text: str, limit: int = 90) -> str:
    line = (text or "").strip().splitlines()[0] if text.strip() else ""
    line = line.strip("*_# ").strip()
    return (line[:limit] + "…") if len(line) > limit else line


async def fetch_own_posts(days: int | None = None) -> list[dict]:
    """Возвращает наши посты за период с метриками просмотров/реакций/репостов."""
    if not configured():
        raise RuntimeError("Telethon не настроен (нет API_ID/API_HASH/сессии).")
    days = days or config.MONTHLY_LOOKBACK_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    client = TelegramClient(
        StringSession(config.TELETHON_SESSION),
        int(config.TELETHON_API_ID), config.TELETHON_API_HASH,
    )
    posts: list[dict] = []
    await client.connect()
    try:
        async for msg in client.iter_messages(config.CHANNEL_USERNAME, limit=400):
            if msg.date and msg.date < cutoff:
                break
            text = msg.message or ""
            if not text.strip():
                continue
            reactions = 0
            if getattr(msg, "reactions", None) and msg.reactions.results:
                reactions = sum(r.count for r in msg.reactions.results)
            posts.append({
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else "",
                "headline": _first_line(text),
                "text": text[:800],
                "views": int(getattr(msg, "views", 0) or 0),
                "reactions": reactions,
                "forwards": int(getattr(msg, "forwards", 0) or 0),
                "url": f"https://t.me/{config.CHANNEL_USERNAME}/{msg.id}",
            })
    finally:
        await client.disconnect()
    log.info("Прочитано %d наших постов за %d дн.", len(posts), days)
    return posts


def _score(p: dict) -> int:
    return p["views"] + p["reactions"] * 20 + p["forwards"] * 30


def rank(posts: list[dict]) -> list[dict]:
    return sorted(posts, key=_score, reverse=True)


async def performance_summary(top: int = 5) -> str:
    """Короткая сводка «что заходило» для утреннего подбора. Пусто, если не настроено."""
    if not (configured() and config.USE_STATS_LOOP):
        return ""
    try:
        posts = await fetch_own_posts(days=30)
    except Exception as e:  # noqa: BLE001
        log.warning("Статистику не получил: %s", e)
        return ""
    if not posts:
        return ""
    best = rank(posts)[:top]
    lines = [f"- «{p['headline']}» — {p['views']} просм., {p['reactions']} реакц." for p in best]
    return "Недавно у нас лучше всего заходило (учитывай при подборе):\n" + "\n".join(lines)
