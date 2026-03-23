"""
Configuration settings for the Quiz Bot system.
"""
import os
from pathlib import Path

# Telegram Bot Token - set via environment variable or replace directly
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8764719096:AAEvBC8vhurWPDrUCBHOCTjFMrbv-pZ2Yak")

# Scraping settings
BASE_URL = "[6799ad7a0ea7b.xvest4.ru](https://6799ad7a0ea7b.xvest4.ru/ReadyForExam/ReadyForExam/index.php)"
SCRAPE_PARAMS = {
    "page": "fulltest",
    "slug": "korporativ-boshqaruv-1",
    "session": "4D92718D"
}

# Data storage
DATA_DIR = Path(__file__).parent / "data"
QUESTIONS_PER_TEST = 25

# Request settings
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.5  # Delay between requests to avoid overloading server
MAX_RETRIES = 3

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)
