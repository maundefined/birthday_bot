import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import Database
from services.scheduler import BirthdayScheduler

# Импортируем роутеры
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.birthday import router as birthday_router
from handlers.barcode import router as barcode_router
from handlers.admin import router as admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    # Инициализация базы данных
    db = Database()
    logger.info("База данных инициализирована")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(birthday_router)
    dp.include_router(barcode_router)
    dp.include_router(admin_router)
    
    # Запуск планировщика
    scheduler = BirthdayScheduler(bot)
    scheduler_task = asyncio.create_task(scheduler.start())
    
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await scheduler.stop()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())