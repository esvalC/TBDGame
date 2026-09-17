"""App configuration. Override anything here with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-before-you-put-this-on-the-internet")
    GAME_TITLE = os.environ.get("GAME_TITLE", "Blanks")

    # >>> CARD PACKS LIVE HERE <<<  (every *.json in this folder is loaded)
    PACKS_DIR = Path(os.environ.get("PACKS_DIR", BASE_DIR / "data" / "packs"))

    DEFAULT_HAND_SIZE = int(os.environ.get("HAND_SIZE", 10))
    DEFAULT_POINTS_TO_WIN = int(os.environ.get("POINTS_TO_WIN", 5))
    GAME_TTL_SECONDS = int(os.environ.get("GAME_TTL_SECONDS", 6 * 3600))
    POLL_INTERVAL_MS = int(os.environ.get("POLL_INTERVAL_MS", 1500))


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
