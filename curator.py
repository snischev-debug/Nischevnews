"""Вызов Claude: из собранных новостей делаем ТОП-N с комментариями."""
import json
import logging

from anthropic import AsyncAnthropic

import config
import editor_prompt

log = logging.getLogger("curator")
_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)


def _extract_json(text: str) -> dict:
    """На случай, если модель всё же обернёт ответ в ```json ... ```."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1:
        t = t[start : end + 1]
    return json.loads(t)


async def curate(items: list[dict]) -> dict:
    if not items:
        return {"editor_note": "Свежих материалов по темам канала не нашлось.", "items": []}

    resp = await _client.messages.create(
        model=config.MODEL,
        max_tokens=4000,
        system=editor_prompt.build_system_prompt(),
        messages=[{"role": "user", "content": editor_prompt.build_user_prompt(items)}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text")

    try:
        data = _extract_json(raw)
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось распарсить ответ модели: %s\n%s", e, raw[:500])
        raise

    data["items"] = data.get("items", [])[: config.TOP_N]
    log.info("Отобрано %d материалов в ТОП", len(data["items"]))
    return data
