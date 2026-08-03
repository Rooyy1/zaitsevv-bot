"""
Точка входа. Запуск: python bot.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import BOT_TOKEN
from scheduler import scheduler_loop

import handlers
import admin
import broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в переменных окружения (.env)")

    await db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # порядок важен: сначала более специфичные админ-роутеры, потом общий
    dp.include_router(admin.router)
    dp.include_router(broadcast.router)
    dp.include_router(handlers.router)

    # фоновая задача — сканирует БД и шлёт то, что созрело по времени
    scheduler_task = asyncio.create_task(scheduler_loop(bot))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот запущен, начинаю polling")
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
