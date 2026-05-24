"""Discord bot factory and entrypoint."""

import logging

import discord
from discord.ext import commands

from src.ai.client import AiClient
from src.config import settings
from src.config.secrets import loadSecrets
from src.discord_ui.commands import TradingCommands
from src.exchange.factory import createFuturesExchange

logger = logging.getLogger(__name__)


def createBot() -> commands.Bot:
    """
    Create Discord bot instance.
    Intents: message_content, guilds.
    Prefix: tidak ada — pakai slash commands saja.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.presences = True
    intents.members = True
    return commands.Bot(
        command_prefix=commands.when_mentioned,
        intents=intents,
        status=discord.Status.online,
        activity=discord.Game(name="Trading 📈"),
    )


async def startBot(token: str) -> None:
    """Start bot, load commands cog."""
    secrets = loadSecrets()
    authorizedUserId = int(secrets.get("DISCORD_USER_ID", "0"))
    guildId: int | None = int(gid) if (gid := secrets.get("DISCORD_GUILD_ID")) else None

    futuresExchange = createFuturesExchange(testnet=settings.USE_TESTNET)
    aiClient = AiClient(
        baseUrl=secrets.get("AI_BASE_URL", ""),
        apiKey=secrets.get("AI_API_KEY", ""),
        model=secrets.get("AI_MODEL", ""),
    )

    bot = createBot()
    await bot.add_cog(TradingCommands(bot, futuresExchange, aiClient, authorizedUserId))

    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception) -> None:  # type: ignore[type-arg]
        """Suppress CommandNotFound — bot uses slash commands only."""
        if isinstance(error, commands.CommandNotFound):
            return
        logger.error("Command error: %s", error)

    @bot.event
    async def on_ready() -> None:
        """Sync slash commands on connect."""
        if guildId is not None:
            guild = discord.Object(id=guildId)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info("Slash commands synced to guild %d", guildId)
        else:
            await bot.tree.sync()
            logger.info("Slash commands synced globally")
        logger.info("Discord bot ready as %s", bot.user)

    await bot.start(token)
