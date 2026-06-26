"""Telegram-бот-редакция для канала @nishchev.

Бот не публикует в канал сам. Присылает ТЕБЕ в личку:
  • каждое утро — подборку/идеи под РУБРИКУ ДНЯ с кнопками «✍️ Сделать пост»;
  • в течение дня — «⚡ Молнию» по свежему зарубежному эксклюзиву;
  • раз в месяц — готовый «📅 Дайджест месяца» из НАШИХ постов канала.
При сборке поста добавляет идею опроса для вовлечения; в подборе учитывает,
что у нас уже заходило (петля по статистике).

Команды: /start /digest /today /post N /flash /monthly
"""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import rubrics
import fetcher
import formatter
import writer
import telegraph
import seen_store
import channel_reader
import imagegen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# последняя подборка по чату: chat_id -> (items, rubric)
_last: dict[int, tuple[list[dict], dict]] = {}


def _is_admin(chat_id: int) -> bool:
    return chat_id in config.ADMIN_CHAT_IDS


def today_rubric(force_weekday: int | None = None) -> dict:
    if force_weekday is not None:
        return rubrics.for_weekday(force_weekday)
    wd = datetime.now(ZoneInfo(config.TIMEZONE)).weekday()
    return rubrics.for_weekday(wd)


async def _send_all(messages: list[str]):
    for chat_id in config.ADMIN_CHAT_IDS:
        for m in messages:
            await bot.send_message(chat_id, m, disable_web_page_preview=True)
            await asyncio.sleep(0.4)


def _item_keyboard(n: int) -> InlineKeyboardMarkup:
    post_row = [InlineKeyboardButton(text=f"✍️ Пост {i+1}", callback_data=f"post:{i}") for i in range(n)]
    img_row = [InlineKeyboardButton(text=f"🖼 {i+1}", callback_data=f"img:{i}") for i in range(n)]
    rows = [post_row[i:i + 3] for i in range(0, len(post_row), 3)]
    rows += [img_row[i:i + 5] for i in range(0, len(img_row), 5)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Утренняя подборка под рубрику дня ─────────────────────────────
async def daily_digest(force_weekday: int | None = None):
    rub = today_rubric(force_weekday)
    perf = await channel_reader.performance_summary()
    items = await fetcher.fetch_all()
    data = await writer.daily_rubric(rub, items, perf)
    messages = formatter.render_daily(data, rub["label"])
    picked = data.get("items", [])
    for chat_id in config.ADMIN_CHAT_IDS:
        for m in messages:
            await bot.send_message(chat_id, m, disable_web_page_preview=True)
            await asyncio.sleep(0.4)
        _last[chat_id] = (picked, rub)
        if picked:
            await bot.send_message(chat_id, "Собрать пост (✍️) или картинку (🖼) по теме:",
                                   reply_markup=_item_keyboard(len(picked)))


# ── Полный пост + лонгрид + опрос ─────────────────────────────────
async def make_full_post(chat_id: int, item: dict, rubric: dict):
    await bot.send_message(chat_id, "Пишу пост…")
    draft = await writer.write_full_post(item, rubric)

    text = draft.get("post_text") or "Пусто."
    if draft.get("longread_blocks"):
        try:
            url = await telegraph.create_page(
                draft.get("longread_title") or "Лонгрид",
                draft["longread_blocks"], item.get("url", ""))
            text += f"\n\n📖 Лонгрид: {url}"
        except Exception as e:  # noqa: BLE001
            log.warning("Telegraph: %s", e)
    await bot.send_message(chat_id, text, parse_mode=None, disable_web_page_preview=True)

    poll = draft.get("poll")
    if poll and poll.get("question"):
        opts = "\n".join(f"— {o}" for o in poll.get("options", []))
        await bot.send_message(
            chat_id, f"📊 Опрос для вовлечения:\n{poll['question']}\n{opts}", parse_mode=None)


# ── Картинка по теме (Nano Banana Pro) ────────────────────────────
async def make_image(chat_id: int, item: dict, rubric: dict):
    if not imagegen.configured():
        await bot.send_message(
            chat_id, "Генерация картинок не настроена: добавь GEMINI_API_KEY (см. UPGRADE3.md).")
        return
    await bot.send_message(chat_id, "Рисую картинку, до минуты…")
    prompt = await writer.image_prompt_for(item, rubric)
    img = await imagegen.generate(prompt)
    caption = (item.get("headline") or item.get("title") or "")[:1000]
    await bot.send_photo(chat_id, BufferedInputFile(img, filename="cover.png"), caption=caption)


# ── Молния ────────────────────────────────────────────────────────
async def flash_scan(manual_chat: int | None = None):
    items = await fetcher.fetch_all(lookback_hours=config.FLASH_LOOKBACK_HOURS)
    seen = seen_store.load()
    candidates = [it for it in items if it["origin"] == "foreign" and it["url"] not in seen]
    if not candidates:
        if manual_chat:
            await bot.send_message(manual_chat, "Новых зарубежных эксклюзивов нет.")
        return
    res = await writer.pick_and_write_flash(candidates)
    if res["worth"] and 0 <= res["index"] < len(candidates):
        chosen = candidates[res["index"]]
        seen_store.add([chosen["url"]])
        await _send_all(["<b>⚡ Молния — готов к публикации</b> 🌍\n\n" + formatter._esc(res["post_text"])])
    else:
        seen_store.add([c["url"] for c in candidates])
        if manual_chat:
            await bot.send_message(manual_chat, "Стоящего эксклюзива сейчас нет.")


# ── Месячный дайджест НАШИХ постов ────────────────────────────────
async def monthly_digest(manual_chat: int | None = None):
    if not channel_reader.configured():
        note = ("Месячный дайджест читает наш канал — для этого нужен доступ через Telethon "
                "(API_ID/API_HASH и сессия). См. UPGRADE2.md, раздел про месячный дайджест.")
        await (bot.send_message(manual_chat, note) if manual_chat else _send_all([note]))
        return
    posts = await channel_reader.fetch_own_posts(config.MONTHLY_LOOKBACK_DAYS)
    if not posts:
        msg = "За месяц не нашёл наших постов для дайджеста."
        await (bot.send_message(manual_chat, msg) if manual_chat else _send_all([msg]))
        return
    data = await writer.write_monthly_own(posts)
    messages = formatter.render_monthly(data)
    await _send_all(["<b>Готов к публикации дайджест месяца ⬇️</b>"] + messages)


# ── Команды ───────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(m: Message):
    if not _is_admin(m.chat.id):
        await m.answer(f"Твой chat_id: <code>{m.chat.id}</code>")
        return
    rub = today_rubric()
    await m.answer(
        "Я на связи. Что делаю:\n"
        f"• утром {config.DIGEST_HOUR:02d}:{config.DIGEST_MINUTE:02d} — подборка под рубрику дня;\n"
        f"• днём каждые {config.FLASH_INTERVAL_HOURS} ч — ⚡ молнии по зарубежным эксклюзивам;\n"
        f"• раз в месяц — 📅 дайджест наших постов.\n\n"
        f"Сегодня рубрика: <b>{rub['label']}</b>.\n"
        "Команды: /digest, /today, /post N, /generate N, /flash, /monthly"
    )


@dp.message(Command("digest"))
@dp.message(Command("today"))
async def cmd_digest(m: Message):
    if not _is_admin(m.chat.id):
        return
    await m.answer("Собираю подборку под сегодняшнюю рубрику…")
    try:
        await daily_digest()
    except Exception as e:  # noqa: BLE001
        log.exception("digest"); await m.answer(f"Упал: {e}")


@dp.message(Command("post"))
async def cmd_post(m: Message):
    if not _is_admin(m.chat.id):
        return
    parts = (m.text or "").split()
    pair = _last.get(m.chat.id)
    if not pair:
        await m.answer("Сначала собери подборку: /digest"); return
    items, rub = pair
    if len(parts) < 2 or not parts[1].isdigit():
        await m.answer("Укажи номер темы, например: /post 1"); return
    idx = int(parts[1]) - 1
    if not (0 <= idx < len(items)):
        await m.answer(f"Есть темы с 1 по {len(items)}."); return
    try:
        await make_full_post(m.chat.id, items[idx], rub)
    except Exception as e:  # noqa: BLE001
        log.exception("post"); await m.answer(f"Упал: {e}")


@dp.message(Command("generate"))
async def cmd_generate(m: Message):
    if not _is_admin(m.chat.id):
        return
    parts = (m.text or "").split()
    pair = _last.get(m.chat.id)
    if not pair:
        await m.answer("Сначала собери подборку: /digest"); return
    items, rub = pair
    if len(parts) < 2 or not parts[1].isdigit():
        await m.answer("Укажи номер новости, например: /generate 1"); return
    idx = int(parts[1]) - 1
    if not (0 <= idx < len(items)):
        await m.answer(f"Есть темы с 1 по {len(items)}."); return
    try:
        await make_image(m.chat.id, items[idx], rub)
    except Exception as e:  # noqa: BLE001
        log.exception("generate"); await m.answer(f"Упал: {e}")


@dp.message(Command("flash"))
async def cmd_flash(m: Message):
    if not _is_admin(m.chat.id):
        return
    await m.answer("Проверяю эксклюзивы…")
    try:
        await flash_scan(manual_chat=m.chat.id)
    except Exception as e:  # noqa: BLE001
        log.exception("flash"); await m.answer(f"Упал: {e}")


@dp.message(Command("monthly"))
async def cmd_monthly(m: Message):
    if not _is_admin(m.chat.id):
        return
    await m.answer("Собираю дайджест месяца из наших постов…")
    try:
        await monthly_digest(manual_chat=m.chat.id)
    except Exception as e:  # noqa: BLE001
        log.exception("monthly"); await m.answer(f"Упал: {e}")


# ── Кнопки «Сделать пост» ─────────────────────────────────────────
@dp.callback_query(F.data.startswith("post:"))
async def cb_post(c: CallbackQuery):
    if not _is_admin(c.message.chat.id):
        return
    idx = int(c.data.split(":", 1)[1])
    pair = _last.get(c.message.chat.id)
    if not pair or not (0 <= idx < len(pair[0])):
        await c.answer("Подборка устарела, собери /digest", show_alert=True); return
    items, rub = pair
    await c.answer("Делаю пост…")
    try:
        await make_full_post(c.message.chat.id, items[idx], rub)
    except Exception as e:  # noqa: BLE001
        log.exception("cb_post")
        await bot.send_message(c.message.chat.id, f"Упал: {e}")


@dp.callback_query(F.data.startswith("img:"))
async def cb_img(c: CallbackQuery):
    if not _is_admin(c.message.chat.id):
        return
    idx = int(c.data.split(":", 1)[1])
    pair = _last.get(c.message.chat.id)
    if not pair or not (0 <= idx < len(pair[0])):
        await c.answer("Подборка устарела, собери /digest", show_alert=True); return
    items, rub = pair
    await c.answer("Рисую…")
    try:
        await make_image(c.message.chat.id, items[idx], rub)
    except Exception as e:  # noqa: BLE001
        log.exception("cb_img")
        await bot.send_message(c.message.chat.id, f"Упал: {e}")


# ── Планировщик ───────────────────────────────────────────────────
async def main():
    sch = AsyncIOScheduler(timezone=config.TIMEZONE)
    sch.add_job(daily_digest, "cron", hour=config.DIGEST_HOUR, minute=config.DIGEST_MINUTE)
    if config.FLASH_INTERVAL_HOURS > 0:
        sch.add_job(flash_scan, "interval", hours=config.FLASH_INTERVAL_HOURS)
    sch.add_job(monthly_digest, "cron", day=config.MONTHLY_DAY,
                hour=config.MONTHLY_HOUR, minute=config.MONTHLY_MINUTE)
    sch.start()
    log.info("Бот запущен. Утро %02d:%02d, молния каждые %s ч, дайджест месяца %s-го %02d:%02d (%s)",
             config.DIGEST_HOUR, config.DIGEST_MINUTE, config.FLASH_INTERVAL_HOURS,
             config.MONTHLY_DAY, config.MONTHLY_HOUR, config.MONTHLY_MINUTE, config.TIMEZONE)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
