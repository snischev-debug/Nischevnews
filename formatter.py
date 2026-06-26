"""Сборка утреннего сообщения-советника для Telegram из JSON редактора."""
import html

TELEGRAM_LIMIT = 4096

THEME_LABEL = {
    "leadership": "Лидерство",
    "marketing": "Маркетинг",
    "digital_transformation": "Цифровая трансформация",
    "robotization": "Роботизация",
}


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def render(data: dict) -> list[str]:
    """Список сообщений с учётом лимита Telegram (4096)."""
    note = _esc(data.get("editor_note", "")).strip()
    items = data.get("items", [])

    header = "<b>☀️ Утренний разбор: свежие темы для канала</b>"
    if note:
        header += f"\n\n{note}"

    blocks = [header]
    for it in items:
        rank = it.get("rank", "")
        flag = " 🌍 <i>эксклюзив</i>" if it.get("exclusive") else ""
        theme = THEME_LABEL.get(it.get("theme", ""), "")
        headline = _esc(it.get("headline", ""))
        summary = _esc(it.get("summary", ""))
        angle = _esc(it.get("angle", ""))
        why = _esc(it.get("why_audience", ""))
        url = it.get("url", "")
        source = _esc(it.get("source_name", ""))

        block = (
            f"<b>{rank}. {headline}</b>{flag}\n"
            f"{summary}\n\n"
            f"💡 <b>Как обыграть:</b> {angle}\n"
            f"🎯 <b>Почему зайдёт:</b> {why}\n"
            f"🔗 <a href=\"{html.escape(url, quote=True)}\">{source}</a>"
        )
        if theme:
            block += f"  ·  <i>{theme}</i>"
        blocks.append(block)

    blocks.append("Скажи, какую тему развернуть — соберём из неё пост.")

    messages, current = [], ""
    for b in blocks:
        candidate = b if not current else current + "\n\n" + b
        if len(candidate) > TELEGRAM_LIMIT:
            if current:
                messages.append(current)
            current = b
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def render_weekly(data: dict) -> list[str]:
    """Готовый к публикации пост «ТОП недели»."""
    intro = _esc(data.get("intro", "")).strip()
    outro = _esc(data.get("outro", "")).strip()
    items = data.get("items", [])

    head = "<b>🏆 ТОП недели</b>"
    if intro:
        head += f"\n\n{intro}"
    blocks = [head]

    for n, it in enumerate(items, 1):
        flag = " 🌍" if it.get("exclusive") else ""
        headline = _esc(it.get("headline", ""))
        blurb = _esc(it.get("blurb", ""))
        url = it.get("url", "")
        source = _esc(it.get("source_name", ""))
        block = (
            f"<b>{n}. {headline}</b>{flag}\n"
            f"{blurb}\n"
            f"🔗 <a href=\"{html.escape(url, quote=True)}\">{source}</a>"
        )
        blocks.append(block)

    if outro:
        blocks.append(outro)

    messages, current = [], ""
    for b in blocks:
        candidate = b if not current else current + "\n\n" + b
        if len(candidate) > TELEGRAM_LIMIT:
            if current:
                messages.append(current)
            current = b
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def render_daily(data: dict, rubric_label: str) -> list[str]:
    """Утренняя подборка/идеи под рубрику дня (ссылка показывается, только если есть url)."""
    intro = _esc(data.get("intro", "")).strip()
    items = data.get("items", [])

    header = f"☀️ <b>{_esc(rubric_label)}</b>"
    if intro:
        header += f"\n\n{intro}"
    blocks = [header]

    for n, it in enumerate(items, 1):
        flag = " 🌍 <i>эксклюзив</i>" if it.get("exclusive") else ""
        headline = _esc(it.get("headline", ""))
        summary = _esc(it.get("summary", ""))
        angle = _esc(it.get("angle", ""))
        why = _esc(it.get("why_audience", ""))
        url = it.get("url", "")
        source = _esc(it.get("source_name", ""))

        block = f"<b>{n}. {headline}</b>{flag}\n{summary}\n\n💡 <b>Как обыграть:</b> {angle}"
        if why:
            block += f"\n🎯 <b>Почему зайдёт:</b> {why}"
        if url:
            block += f"\n🔗 <a href=\"{html.escape(url, quote=True)}\">{source or 'источник'}</a>"
        blocks.append(block)

    blocks.append("Жми «✍️ Пост N» — соберу готовый пост по теме.")
    return _pack(blocks)


def render_monthly(data: dict) -> list[str]:
    intro = _esc(data.get("intro", "")).strip()
    outro = _esc(data.get("outro", "")).strip()
    items = data.get("items", [])

    head = "📅 <b>Дайджест месяца — лучшее из канала</b>"
    if intro:
        head += f"\n\n{intro}"
    blocks = [head]
    for n, it in enumerate(items, 1):
        headline = _esc(it.get("headline", ""))
        blurb = _esc(it.get("blurb", ""))
        url = it.get("url", "")
        line = f"<b>{n}. {headline}</b>\n{blurb}"
        if url:
            line += f"\n🔗 <a href=\"{html.escape(url, quote=True)}\">читать</a>"
        blocks.append(line)
    if outro:
        blocks.append(outro)
    return _pack(blocks)


def _pack(blocks: list[str]) -> list[str]:
    messages, current = [], ""
    for b in blocks:
        candidate = b if not current else current + "\n\n" + b
        if len(candidate) > TELEGRAM_LIMIT:
            if current:
                messages.append(current)
            current = b
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages
