"""Discord bot factory and entrypoint."""

import logging

import discord
from discord import app_commands
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

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError,
    ) -> None:
        """Handle stale slash commands that no longer exist in the tree."""
        if isinstance(error, app_commands.CommandNotFound):
            logger.warning("Stale command invoked: %s — run /sync or re-sync guild commands", error)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ Command tidak dikenali. Kemungkinan stale — coba lagi dalam beberapa menit.",
                    ephemeral=True,
                )
            return
        logger.error("App command error: %s", error, exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Internal error.", ephemeral=True)

    @bot.event
    async def on_ready() -> None:
        """Sync slash commands on connect. Clear stale global commands if guild-scoped."""
        if guildId is not None:
            guild = discord.Object(id=guildId)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            # Clear stale global commands (removes 'vc', 'whoami', etc.)
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            logger.info("Slash commands synced to guild %d, global commands cleared", guildId)
        else:
            await bot.tree.sync()
            logger.info("Slash commands synced globally")
        logger.info("Discord bot ready as %s", bot.user)

    await bot.start(token)
