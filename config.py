import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(','))) if os.getenv("ADMIN_IDS") else []

# Конфигурация базы данных
DB_NAME = "birthdays.db"

# Конфигурация напоминаний
REMIND_DAYS_BEFORE = 10
DEFAULT_REMIND_HOUR = 9  # 9:00 утра