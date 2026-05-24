"""Logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configureLogging(logDir: str = "logs") -> logging.Logger:
    """
    Configure logging with file and console handlers.

    - File handler: logs/bot.log (rotating, 10MB, 5 backups)
    - Console handler: INFO level
    - Format: "2026-05-24T06:00:00Z [INFO] module — message"
    """
    Path(logDir).mkdir(exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatStr = "%(asctime)s [%(levelname)s] %(module)s — %(message)s"
    formatter = logging.Formatter(formatStr, datefmt="%Y-%m-%dT%H:%M:%SZ")

    fileHandler = RotatingFileHandler(
        f"{logDir}/bot.log", maxBytes=10_000_000, backupCount=5
    )
    fileHandler.setLevel(logging.DEBUG)
    fileHandler.setFormatter(formatter)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)

    logger.addHandler(fileHandler)
    logger.addHandler(consoleHandler)

    # Suppress DEBUG noise from external libraries
    for noisy in ("discord", "httpx", "httpcore", "ccxt", "asyncio", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger
