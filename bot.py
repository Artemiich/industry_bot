import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from Database.db import create_tables
from handlers import registration, user_menu

# Загружаем переменные из .env
load_dotenv()


async def main():
    logging.basicConfig(level=logging.INFO)

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("Ошибка: Токен не найден в .env")
        return

    bot = Bot(token=bot_token)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(registration.router)
    dp.include_router(user_menu.router)

    # Создаем БД при запуске
    await create_tables()
    print("Бот запущен и БД подключена...")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")