"""Простейшая память «уже отправленного» для режима Молния (дедуп по URL).

Хранится в seen.json рядом с ботом. На Railway файловая система сбрасывается
при передеплое — это не страшно: максимум одна повторная молния после деплоя.
"""
import json
import logging
from config import SEEN_FILE

log = logging.getLogger("seen")
_MAX = 500  # держим последние N url, чтобы файл не рос бесконечно


def load() -> set[str]:
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:  # noqa: BLE001
        return set()


def add(urls: list[str]) -> None:
    seen = load()
    seen.update(u for u in urls if u)
    trimmed = list(seen)[-_MAX:]
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        log.warning("Не смог сохранить seen.json: %s", e)
