from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from .config import load_settings
from .db import configure_database, init_db
from .handlers import admin, user


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    configure_database(settings.database_url)
    await init_db(settings)

    admin.configure(settings)
    user.configure(settings)

    bot = Bot(token=settings.bot_token)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Open the bot"),
            BotCommand(command="stats", description="View global stats"),
            BotCommand(command="p2pstats", description="View your P2P stats"),
            BotCommand(command="cancel", description="Cancel the current flow"),
        ]
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(admin.router)
    dispatcher.include_router(user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
