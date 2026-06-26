"""«Писатель»: готовый к публикации контент в голосе автора, с учётом рубрики дня.

Функции:
  pick_and_write_flash(candidates)        — молния: лучший зарубежный эксклюзив → короткий пост.
  daily_rubric(rubric, items, perf)       — подборка/идеи под рубрику дня.
  write_full_post(item, rubric)           — полный пост (+ лонгрид, + опрос) под рубрику.
  write_monthly_own(posts)                — месячный дайджест НАШИХ постов канала.
"""
import json
import logging

from anthropic import AsyncAnthropic

import config

log = logging.getLogger("writer")
_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)


def _audience() -> str:
    with open(config.AUDIENCE_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1:
        t = t[s:e + 1]
    return json.loads(t)


async def _ask(system: str, user: str, max_tokens: int = 3000) -> dict:
    resp = await _client.messages.create(
        model=config.MODEL, max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    return _extract_json(raw)


_VOICE = (
    "Пиши в голосе автора: первое лицо, самоирония, конкретика, короткие фразы, "
    "маркеры мыслей — стрелка →, закрывающий вопрос-рефлексия без морализаторства. "
    "Суть пересказывай СВОИМИ СЛОВАМИ, без копирования источника; цитата, если совсем нужна, "
    "— короче 15 слов. Запрещены «не X, а Y», «Это не X. Это Y.», «Именно поэтому», "
    "«Если упростить», «Это смена парадигмы». Без канцелярита и обилия эмодзи."
)


# ── Молния ────────────────────────────────────────────────────────
async def pick_and_write_flash(candidates: list[dict]) -> dict:
    payload = [
        {"index": i, "title": c["title"], "summary": c["summary"],
         "source_name": c["source_name"], "theme": c["theme"], "url": c["url"]}
        for i, c in enumerate(candidates)
    ]
    system = (
        "Ты — выпускающий редактор Telegram-канала о бизнесе. Тебе дали свежие ЗАРУБЕЖНЫЕ "
        "материалы, которых ещё нет в русскоязычных каналах. Выбери НЕ БОЛЕЕ одного — самый "
        "сильный для «молнии» (быть первым на русском), соосный темам канала. Нет стоящего — "
        "верни worth=false.\n\n"
        f"{_audience()}\n\n{_VOICE}\n\n"
        "Если выбрал — короткий готовый пост (4–8 строк): хук, 2–3 пункта со стрелками →, "
        "закрывающий вопрос, в конце строкой «Источник: <имя>». "
        "Верни СТРОГО JSON: {\"worth\": bool, \"index\": int_или_-1, \"post_text\": \"...\"}"
    )
    user = "Кандидаты:\n\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    data = await _ask(system, user, 1500)
    return {"worth": bool(data.get("worth")), "index": int(data.get("index", -1)),
            "post_text": (data.get("post_text") or "").strip()}


# ── Подборка/идеи под рубрику дня ─────────────────────────────────
async def daily_rubric(rubric: dict, items: list[dict], perf_summary: str = "") -> dict:
    is_news = rubric.get("mode") == "news"
    themes = rubric.get("themes") or []
    perf_block = f"\n\n{perf_summary}" if perf_summary else ""

    if is_news:
        pool = [it for it in items if not themes or it["theme"] in themes] or items
        payload = [
            {"i": i, "title": it["title"], "summary": it["summary"], "url": it["url"],
             "source_name": it["source_name"], "theme": it["theme"], "origin": it["origin"]}
            for i, it in enumerate(pool[:40])
        ]
        system = (
            "Ты — личный контент-скаут автора Telegram-канала. Сегодняшняя рубрика и её стиль:\n"
            f"«{rubric['label']}» — {rubric['style']}\n\n"
            "Отбери 3–4 свежих материала строго под эту рубрику и тему, с приоритетом "
            "зарубежного эксклюзива (origin=foreign без РФ-аналога → exclusive=true). По каждому "
            "дай совет, как обыграть в посте этого дня.\n\n"
            f"{_audience()}\n\n{_VOICE}{perf_block}\n\n"
            "Верни СТРОГО JSON: {\"intro\":\"...\",\"items\":[{\"rank\":1,\"headline\":\"...\","
            "\"summary\":\"...\",\"angle\":\"совет, как обыграть\",\"why_audience\":\"одной строкой\","
            "\"theme\":\"...\",\"exclusive\":bool,\"source_name\":\"...\",\"url\":\"...\"}]}"
        )
        user = "Свежие материалы:\n\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    else:
        # оригинальная рубрика: идеи с нуля, ленты — лишь лёгкая пища для контекста
        seeds = [{"title": it["title"], "theme": it["theme"]} for it in items[:12]]
        system = (
            "Ты — автор Telegram-канала о бизнесе. Сегодняшняя рубрика и её стиль:\n"
            f"«{rubric['label']}» — {rubric['style']}\n\n"
            "Предложи 3 идеи поста именно в этом стиле (новости не обязательны, это твой "
            "авторский день). По каждой: цепляющий заголовок, о чём, и заход/хук.\n\n"
            f"{_audience()}\n\n{_VOICE}{perf_block}\n\n"
            "Верни СТРОГО JSON: {\"intro\":\"...\",\"items\":[{\"rank\":1,\"headline\":\"...\","
            "\"summary\":\"о чём пост\",\"angle\":\"заход/хук\",\"why_audience\":\"одной строкой\","
            "\"theme\":\"\",\"exclusive\":false,\"source_name\":\"\",\"url\":\"\"}]}"
        )
        user = "Лёгкие зацепки из лент (по желанию):\n\n" + json.dumps(seeds, ensure_ascii=False, indent=1)

    data = await _ask(system, user, 3000)
    data.setdefault("intro", "")
    data.setdefault("items", [])
    return data


# ── Полный пост (+ лонгрид, + опрос) под рубрику ──────────────────
async def write_full_post(item: dict, rubric: dict | None = None) -> dict:
    rubric = rubric or {}
    want_longread = bool(rubric.get("longread"))
    style = rubric.get("style", "")
    engage = config.ENGAGEMENT

    longread_spec = (
        "Также собери структуру лонгрида (5–9 блоков) — твой разбор/позиция через "
        "управленческую оптику. Типы блоков: h3, p, quote, ul. Не выдумывай фактов о "
        "новости сверх источника; домысли только свою аналитику."
        if want_longread else
        "Лонгрид НЕ нужен: верни longread_title=\"\" и longread_blocks=[]."
    )
    poll_spec = (
        "Добавь идею опроса для вовлечения: короткий вопрос и 2–4 варианта."
        if engage else
        "Опрос не нужен: poll=null."
    )
    system = (
        "Ты — автор Telegram-канала о бизнесе. Сделай готовый к публикации пост по теме.\n"
        + (f"Стиль сегодняшней рубрики: {style}\n" if style else "")
        + f"\n{_audience()}\n\n{_VOICE}\n\n{longread_spec}\n{poll_spec}\n\n"
        "Верни СТРОГО JSON:\n"
        "{\"post_text\":\"готовый пост (6–12 строк), если есть источник — ссылкой в конце\","
        "\"longread_title\":\"...\",\"longread_blocks\":[{\"type\":\"h3\",\"text\":\"...\"},"
        "{\"type\":\"p\",\"text\":\"...\"},{\"type\":\"quote\",\"text\":\"...\"},"
        "{\"type\":\"ul\",\"items\":[\"...\"]}],"
        "\"poll\":{\"question\":\"...\",\"options\":[\"...\",\"...\"]}}"
    )
    user = "Тема/идея:\n" + json.dumps(
        {"title": item.get("headline") or item.get("title"), "summary": item.get("summary"),
         "angle": item.get("angle", ""), "source_name": item.get("source_name", ""),
         "url": item.get("url", ""), "theme": item.get("theme", "")},
        ensure_ascii=False, indent=1)
    data = await _ask(system, user, 3500)
    data.setdefault("post_text", "")
    data.setdefault("longread_title", "")
    data.setdefault("longread_blocks", [])
    data.setdefault("poll", None)
    return data


# ── Месячный дайджест НАШИХ постов ────────────────────────────────
async def write_monthly_own(posts: list[dict]) -> dict:
    payload = [
        {"headline": p["headline"], "views": p["views"], "reactions": p["reactions"],
         "forwards": p["forwards"], "url": p["url"], "text": p["text"][:300]}
        for p in posts[:60]
    ]
    system = (
        "Ты — автор Telegram-канала о бизнесе. Собери готовый к публикации пост "
        "«Дайджест месяца: лучшее из канала» из НАШИХ уже опубликованных постов. Выбери "
        "6–8 сильнейших (ориентируйся на просмотры/реакции/репосты и пользу), дай по каждому "
        "одну живую строку-подводку и ссылку. Это праздничный итог месяца, тёплый и полезный.\n\n"
        f"{_audience()}\n\n{_VOICE}\n\n"
        "Верни СТРОГО JSON: {\"intro\":\"1–2 предложения\",\"items\":[{\"headline\":\"...\","
        "\"blurb\":\"подводка одной строкой\",\"url\":\"...\"}],\"outro\":\"закрывающая мысль/вопрос\"}"
    )
    user = "Наши посты за месяц с метриками:\n\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    data = await _ask(system, user, 3500)
    data.setdefault("intro", "")
    data.setdefault("items", [])
    data.setdefault("outro", "")
    return data


# ── Визуальный промпт для картинки ────────────────────────────────
async def image_prompt_for(item: dict, rubric: dict | None = None) -> str:
    """Готовит англоязычный промпт для Nano Banana Pro под тему новости/поста."""
    rubric = rubric or {}
    system = (
        "Ты — арт-директор делового Telegram-канала. По теме сделай ОДИН промпт на английском "
        "для image-модели (Nano Banana Pro). Картинка должна быть обложкой поста: современная "
        "редакционная иллюстрация, чисто и премиально, концептуальная метафора темы, мягкий свет, "
        "сдержанная палитра. Без реальных логотипов брендов, без узнаваемых лиц и без водяных "
        "знаков. Можно добавить короткий заголовок-оверлей на русском (не более 3–4 слов), если "
        "это уместно. Формат 16:9.\n\n"
        "Верни СТРОГО JSON: {\"prompt\": \"полный промпт на английском, включая стиль и текст-оверлей\"}"
    )
    user = "Тема:\n" + json.dumps(
        {"title": item.get("headline") or item.get("title"),
         "summary": item.get("summary", ""), "theme": item.get("theme", ""),
         "rubric": rubric.get("label", "")},
        ensure_ascii=False, indent=1)
    data = await _ask(system, user, 800)
    return (data.get("prompt") or "").strip()
