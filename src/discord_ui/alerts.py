"""Background task: tail bot.log and post alerts to Discord on keyword match."""

import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands, tasks

from src.config import settings

logger = logging.getLogger(__name__)


class AlertWatcher(commands.Cog):
    """Periodic log scanner — posts alert to channel on ERROR/CRITICAL/orphan."""

    def __init__(self, bot: commands.Bot, alertChannelId: int) -> None:
        """Store bot + target channel ID for alert posting."""
        self.bot = bot
        self.alertChannelId = alertChannelId
        self._lastPosition: int = 0
        self.watchLog.start()

    async def cog_unload(self) -> None:
        """Stop background task on cog unload."""
        self.watchLog.cancel()

    @tasks.loop(seconds=settings.DISCORD_ALERT_INTERVAL_SECONDS)
    async def watchLog(self) -> None:
        """Read new lines from bot.log since last check. Post matched lines to channel."""
        logPath = Path("logs/bot.log")
        if not logPath.exists():
            return
        try:
            newLines = _readNewLines(logPath, self._lastPosition)
            self._lastPosition = logPath.stat().st_size
        except OSError as e:
            logger.error("Alert watcher failed to read log: %s", e)
            return
        for line in newLines:
            if any(kw in line for kw in settings.DISCORD_ALERT_KEYWORDS):
                await self._postAlert(line.strip())

    @watchLog.before_loop
    async def beforeWatchLog(self) -> None:
        """Wait until bot is ready before starting loop."""
        await self.bot.wait_until_ready()

    async def _postAlert(self, line: str) -> None:
        """Send alert message to configured channel."""
        channel = self.bot.get_channel(self.alertChannelId)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Alert channel %d not found or not a text channel", self.alertChannelId)
            return
        await channel.send(f"⚠️ `{line[:1900]}`")


def _readNewLines(logPath: Path, lastPosition: int) -> list[str]:
    """Read lines appended since lastPosition bytes. Return [] if no new content."""
    currentSize = logPath.stat().st_size
    if currentSize <= lastPosition:
        return []
    with logPath.open(encoding="utf-8") as f:
        f.seek(lastPosition)
        return f.readlines()


async def startAlertWatcher(bot: commands.Bot, alertChannelId: int) -> None:
    """Add AlertWatcher cog to bot. Called from startBot after bot is created."""
    await bot.add_cog(AlertWatcher(bot, alertChannelId))
    logger.info("Alert watcher started on channel %d", alertChannelId)
