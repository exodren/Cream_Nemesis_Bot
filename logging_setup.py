from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from config import BASE_DIR

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "bot.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> Path:
    """
    Console + file logging.
    File rotates every 8 hours into dated .txt backups under logs/.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # when='H', interval=8 → новый файл каждые 8 часов
    # rotated name example: bot.log.2026-08-13_00 (suffix below)
    file_handler = TimedRotatingFileHandler(
        filename=str(LOG_FILE),
        when="H",
        interval=8,
        backupCount=42,  # ~14 дней при ротации раз в 8 часов
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d_%H.txt"
    file_handler.namer = _txt_namer
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.info("Logging initialized. Active file: %s (rotate every 8h)", LOG_FILE)
    return LOG_FILE


def _txt_namer(default_name: str) -> str:
    """
    TimedRotatingFileHandler default: bot.log.2026-08-13_00
    Force .txt extension: bot_2026-08-13_00.txt
    """
    base = Path(default_name)
    # base.name like "bot.log.2026-08-13_00"
    stamp = base.name.replace("bot.log.", "")
    return str(base.parent / f"bot_{stamp}.txt")
