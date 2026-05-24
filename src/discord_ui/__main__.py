"""Entrypoint: python -m src.discord_ui"""

import asyncio
import logging

from src.config.secrets import loadSecrets
from src.discord_ui.bot import startBot
from src.logging_.setup import configureLogging


def main() -> None:
    """Load token and start Discord bot."""
    configureLogging()
    secrets = loadSecrets()
    token = secrets.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not set in ~/.secret/quant-arb-bot/.env")
    logging.info("Starting Discord bot...")
    asyncio.run(startBot(token))


if __name__ == "__main__":
    main()
