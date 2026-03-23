import asyncio
import logging
from aiogram import Bot, Dispatcher
from storage import init_storage
import bot as bot_module

BOT_TOKEN = "8764719096:AAEvBC8vhurWPDrUCBHOCTjFMrbv-pZ2Yak"

async def main():
    # 1. Load/Scrape Data into Memory BEFORE bot starts
    bot_module.memory_db = init_storage()
    
    if not bot_module.memory_db:
        logging.error("No questions available to load. Exiting...")
        return

    # 2. Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(bot_module.router)

    logging.info("Starting bot polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
