"""Entrypoint: python -m src.discord_ui"""

import asyncio

from src.config.secrets import loadSecrets
from src.discord_ui.bot import startBot


def main() -> None:
    """Load token and start Discord bot."""
    secrets = loadSecrets()
    token = secrets.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not set in ~/.secrets/quant-arb-bot/.env")
    asyncio.run(startBot(token))


if __name__ == "__main__":
    main()
