"""Конфигурация агента. Секреты — через переменные окружения (.env)."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- Telegram ---
BOT_TOKEN = os.environ["BOT_TOKEN"]                 # от @BotFather
# Получатели советов. Можно один id или несколько через запятую:
#   ADMIN_CHAT_ID=123456789
#   ADMIN_CHAT_ID=123456789,987654321
ADMIN_CHAT_IDS = [int(x.strip()) for x in os.environ["ADMIN_CHAT_ID"].split(",") if x.strip()]
ADMIN_CHAT_ID = ADMIN_CHAT_IDS[0]  # первый — основной (для совместимости)

# --- Anthropic ---
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.getenv("MODEL", "claude-opus-4-8")       # Opus 4.8 по умолчанию

# --- Расписание утренней подборки ---
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "9"))    # час
DIGEST_MINUTE = int(os.getenv("DIGEST_MINUTE", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# --- Параметры отбора ---
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "36"))       # окно свежести
MAX_ITEMS_TO_LLM = int(os.getenv("MAX_ITEMS_TO_LLM", "60"))   # сколько новостей отдаём модели
TOP_N = int(os.getenv("TOP_N", "5"))

SOURCES_FILE = BASE_DIR / "sources.yaml"
AUDIENCE_FILE = BASE_DIR / "audience.md"

# --- Режим «Молния» (1): ловит свежий зарубежный эксклюзив и шлёт готовый пост ---
FLASH_INTERVAL_HOURS = int(os.getenv("FLASH_INTERVAL_HOURS", "4"))   # как часто сканировать; 0 = выключить
FLASH_LOOKBACK_HOURS = int(os.getenv("FLASH_LOOKBACK_HOURS", "6"))   # окно свежести для молнии

# --- Еженедельный «ТОП недели» (6): готовый пост-дайджест ---
WEEKLY_DAY = os.getenv("WEEKLY_DAY", "fri")                          # день недели (mon..sun)
WEEKLY_HOUR = int(os.getenv("WEEKLY_HOUR", "17"))
WEEKLY_MINUTE = int(os.getenv("WEEKLY_MINUTE", "0"))
WEEKLY_LOOKBACK_HOURS = int(os.getenv("WEEKLY_LOOKBACK_HOURS", "168"))

# --- Подпись лонгридов в Telegra.ph ---
AUTHOR_NAME = os.getenv("AUTHOR_NAME", "Сергей Нищев")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/nishchev")
SEEN_FILE = BASE_DIR / "seen.json"

# --- Вовлечение (опрос/вопрос под пост) ---
ENGAGEMENT = os.getenv("ENGAGEMENT", "true").lower() == "true"

# --- Месячный дайджест НАШИХ постов в канале (требует Telethon, см. ниже) ---
MONTHLY_DAY = os.getenv("MONTHLY_DAY", "1")          # день месяца (число) или "last"
MONTHLY_HOUR = int(os.getenv("MONTHLY_HOUR", "12"))
MONTHLY_MINUTE = int(os.getenv("MONTHLY_MINUTE", "0"))
MONTHLY_LOOKBACK_DAYS = int(os.getenv("MONTHLY_LOOKBACK_DAYS", "31"))

# Чтение собственного канала и его статистики (опционально, расширенная настройка).
# Нужны API_ID/API_HASH с my.telegram.org и пользовательская сессия (см. login_telethon.py).
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "nishchev")   # без @
TELETHON_API_ID = os.getenv("TELETHON_API_ID", "")
TELETHON_API_HASH = os.getenv("TELETHON_API_HASH", "")
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "")
USE_STATS_LOOP = os.getenv("USE_STATS_LOOP", "true").lower() == "true"  # учитывать статистику в подборе

# --- Генерация картинок (Nano Banana Pro = Gemini 3 Pro Image) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview")  # дешевле: gemini-3.1-flash-image-preview
IMAGE_ASPECT = os.getenv("IMAGE_ASPECT", "16:9")
