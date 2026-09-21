"""Configuration and logging setup for the lead generation agent."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

MIN_RECORDS = int(os.getenv("MIN_RECORDS", "20"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))  # Places Text Search returns up to 20/page

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(LOGS_DIR / "agent.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
