"""
Main entry point for the Quiz Bot system.
Handles initialization and startup.
"""
import asyncio
import logging
import sys

from config import BOT_TOKEN, DATA_DIR


def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)


def validate_config():
    """Validate configuration before starting."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        print("ERROR: Please set TELEGRAM_BOT_TOKEN environment variable")
        print("       or update BOT_TOKEN in config.py")
        sys.exit(1)
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)


async def main():
    """Main async entry point."""
    setup_logging()
    validate_config()
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Quiz Bot Starting")
    logger.info("=" * 50)
    
    # Import here to avoid circular imports
    from bot import run_bot
    
    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
