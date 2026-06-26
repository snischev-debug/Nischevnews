"""Мини-клиент Telegra.ph: создаём страницу-лонгрид и получаем ссылку.

Блоки лонгрида приходят в простом виде и маппятся в формат узлов Telegra.ph:
  {"type":"h3","text":...}     -> <h3>
  {"type":"h4","text":...}     -> <h4>
  {"type":"p","text":...}      -> <p>
  {"type":"quote","text":...}  -> <blockquote>
  {"type":"ul","items":[...]}  -> <ul><li>...</li></ul>
"""
import json
import logging
import aiohttp

import config

log = logging.getLogger("telegraph")
_API = "https://api.telegra.ph"
_token: str | None = None


async def _ensure_account(session: aiohttp.ClientSession) -> str:
    global _token
    if _token:
        return _token
    params = {
        "short_name": "nishchev",
        "author_name": config.AUTHOR_NAME,
        "author_url": config.CHANNEL_URL,
    }
    async with session.get(f"{_API}/createAccount", params=params) as r:
        data = await r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph createAccount: {data}")
    _token = data["result"]["access_token"]
    return _token


def _to_nodes(blocks: list[dict]) -> list:
    nodes = []
    for b in blocks:
        t = b.get("type")
        if t in ("h3", "h4", "p"):
            nodes.append({"tag": t, "children": [b.get("text", "")]})
        elif t == "quote":
            nodes.append({"tag": "blockquote", "children": [b.get("text", "")]})
        elif t == "ul":
            lis = [{"tag": "li", "children": [it]} for it in b.get("items", [])]
            nodes.append({"tag": "ul", "children": lis})
        else:  # неизвестный тип — как абзац
            nodes.append({"tag": "p", "children": [b.get("text", "")]})
    return nodes


async def create_page(title: str, blocks: list[dict], source_url: str = "") -> str:
    """Создаёт страницу и возвращает её URL."""
    nodes = _to_nodes(blocks)
    if source_url:
        nodes.append({"tag": "p", "children": [
            "Источник: ", {"tag": "a", "attrs": {"href": source_url}, "children": [source_url]}
        ]})
    async with aiohttp.ClientSession() as session:
        token = await _ensure_account(session)
        payload = {
            "access_token": token,
            "title": title[:256] or "Лонгрид",
            "author_name": config.AUTHOR_NAME,
            "author_url": config.CHANNEL_URL,
            "content": json.dumps(nodes, ensure_ascii=False),
            "return_content": "false",
        }
        async with session.post(f"{_API}/createPage", data=payload) as r:
            data = await r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph createPage: {data}")
    return data["result"]["url"]
