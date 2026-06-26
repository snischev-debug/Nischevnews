"""Генерация картинок через Nano Banana Pro (Gemini 3 Pro Image).

Эндпоинт Google: generativelanguage. В ответе картинка приходит base64 внутри
candidates[].content.parts[].inlineData.data.
Pro-модель платная (нужен Google-ключ с включённым биллингом).
"""
import base64
import logging
import aiohttp

import config

log = logging.getLogger("imagegen")
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def configured() -> bool:
    return bool(config.GEMINI_API_KEY)


async def generate(prompt: str, aspect: str | None = None) -> bytes:
    """Возвращает PNG-байты по текстовому промпту."""
    if not configured():
        raise RuntimeError("GEMINI_API_KEY не задан — генерация картинок выключена.")
    url = _ENDPOINT.format(model=config.IMAGE_MODEL)
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect or config.IMAGE_ASPECT},
        },
    }
    headers = {"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as r:
            data = await r.json()

    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])

    raise RuntimeError(f"Картинка не вернулась. Ответ: {str(data)[:300]}")
