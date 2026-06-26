"""Разовый скрипт: получить строку сессии Telethon для чтения своего канала.

Нужен только для месячного дайджеста и петли по статистике.
Запусти ЛОКАЛЬНО (не на Railway):  python login_telethon.py
Понадобятся API_ID и API_HASH с https://my.telegram.org → API development tools,
а также твой телефон и код подтверждения из Telegram.

В конце скрипт напечатает TELETHON_SESSION — длинную строку. Её (и API_ID/API_HASH)
впиши в переменные Railway.
"""
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: ").strip())
api_hash = input("API_HASH: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nГотово. Скопируй строку ниже в переменную TELETHON_SESSION:\n")
    print(client.session.save())
