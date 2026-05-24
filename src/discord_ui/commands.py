"""Slash command handlers for Discord trading bot."""

import logging
from typing import Any

import ccxt
import discord
from discord import app_commands
from discord.ext import commands

from src.ai.client import AiClient
from src.ai.context_builder import buildContext, summarizeRecentLogs
from src.discord_ui.formatter import (
    formatMetricsEmbed,
    formatPositionsEmbed,
    formatStatusEmbed,
    formatTradesEmbed,
)
from src.logging_.trade_log import loadTradeLog
from src.market.cost_cache import CostCache
from src.position.balance import fetchFuturesBalance
from src.position.tracker import fetchOpenPositions

logger = logging.getLogger(__name__)


class TradingCommands(commands.Cog):
    """Slash commands cog — all commands are read-only against trading state."""

    def __init__(self, bot: commands.Bot, futuresExchange: ccxt.binanceusdm,
                 aiClient: AiClient, authorizedUserId: int) -> None:
        """Store bot deps: exchange, AI client, authorized user ID."""
        self.bot = bot
        self.futuresExchange = futuresExchange
        self.aiClient = aiClient
        self.authorizedUserId = authorizedUserId

    def _isAuthorized(self, interaction: discord.Interaction) -> bool:
        """True if interaction user matches authorizedUserId."""
        return interaction.user.id == self.authorizedUserId

    @app_commands.command(name="status", description="Bot status: balance, positions, last cycle.")
    async def statusCommand(self, interaction: discord.Interaction) -> None:
        """Show: open positions, uptime, last cycle time, balance."""
        if not self._isAuthorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        await interaction.response.defer()
        positions: list[dict[str, Any]] = fetchOpenPositions(self.futuresExchange)
        balance = fetchFuturesBalance(self.futuresExchange)
        status: dict[str, object] = {"balance": f"{balance:.2f}", "openPositions": len(positions),
                                     "lastCycle": _parseLastCycleFromLog(), "uptime": "N/A"}
        await interaction.followup.send(embed=formatStatusEmbed(status))

    @app_commands.command(name="positions", description="All open positions with entry, PnL, side.")
    async def positionsCommand(self, interaction: discord.Interaction) -> None:
        """Show detail semua open positions: symbol, side, entry FR, unrealized PnL."""
        if not self._isAuthorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        await interaction.response.defer()
        positions_: list[dict[str, Any]] = fetchOpenPositions(self.futuresExchange)
        await interaction.followup.send(embed=formatPositionsEmbed(positions_))

    @app_commands.command(name="metrics", description="Performance metrics from trade log.")
    async def metricsCommand(self, interaction: discord.Interaction) -> None:
        """Parse trades.jsonl, hitung: total net $, fill rate, win/loss, avg cost, drawdown."""
        if not self._isAuthorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.followup.send(embed=formatMetricsEmbed(_computeMetrics(loadTradeLog())))

    @app_commands.command(name="trades", description="Recent trades from log.")
    @app_commands.describe(limit="Number of recent trades to show (default 10).")
    async def tradesCommand(self, interaction: discord.Interaction, limit: int = 10) -> None:
        """Show last N trades dari trade log."""
        if not self._isAuthorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.followup.send(embed=formatTradesEmbed(loadTradeLog()[-limit:]))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Respond to bot mention with AI answer. Authorized user only."""
        if message.author.bot or self.bot.user is None:
            return
        if self.bot.user not in message.mentions:
            return
        if message.author.id != self.authorizedUserId:
            await message.reply("Unauthorized.")
            return
        question = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
        if not question:
            await message.reply("Tanya apa?")
            return
        async with message.channel.typing():
            botState: dict[str, object] = {
                "openPositions": fetchOpenPositions(self.futuresExchange),
                "availableBalance": fetchFuturesBalance(self.futuresExchange),
                "trades": loadTradeLog(), "costCache": CostCache(), "logPath": "logs/bot.log",
            }
            try:
                response = await self.aiClient.chat(buildContext(botState, question))
            except Exception as e:
                logger.error("AI mention request failed: %s", e)
                response = f"AI unavailable: {e}"
        await message.reply(response[:2000])

    @app_commands.command(name="health", description="Quick health check.")
    async def healthCommand(self, interaction: discord.Interaction) -> None:
        """Quick health check: last cycle, balance, unprotected positions."""
        if not self._isAuthorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        await interaction.response.defer()
        positions: list[dict[str, Any]] = fetchOpenPositions(self.futuresExchange)
        balance = fetchFuturesBalance(self.futuresExchange)
        recentLogs = summarizeRecentLogs("logs/bot.log", lines=20)
        hasErrors = any(kw in recentLogs for kw in ("ERROR", "CRITICAL"))
        embed = discord.Embed(title="🏥 Health Check",
                              color=discord.Color.red() if hasErrors else discord.Color.green())
        embed.add_field(name="Balance", value=f"`${balance:.2f}`", inline=True)
        embed.add_field(name="Open Positions", value=f"`{len(positions)}`", inline=True)
        embed.add_field(name="Last Cycle", value=f"`{_parseLastCycleFromLog()}`", inline=True)
        embed.add_field(name="Errors in Log", value="`Yes`" if hasErrors else "`No`", inline=True)
        await interaction.followup.send(embed=embed)


def _computeMetrics(trades: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate trade log into metrics dict for formatMetricsEmbed."""
    if not trades:
        return {"totalNetDollar": 0.0, "tradeCount": 0, "wins": 0, "losses": 0,
                "avgCostRtPct": 0.0, "fillRate": 0.0, "maxDrawdown": 0.0}
    netValues = [float(t.get("net_dollar", 0)) for t in trades]  # type: ignore[arg-type]
    costs = [float(t.get("cost_rt_pct", 0)) for t in trades]  # type: ignore[arg-type]
    wins = sum(1 for n in netValues if n > 0)
    cumulative, peak, maxDD = 0.0, 0.0, 0.0
    for n in netValues:
        cumulative += n
        peak = max(peak, cumulative)
        maxDD = max(maxDD, peak - cumulative)
    return {"totalNetDollar": sum(netValues), "tradeCount": len(trades), "wins": wins,
            "losses": len(trades) - wins, "avgCostRtPct": sum(costs) / len(costs) if costs else 0.0,
            "fillRate": (wins / len(trades)) * 100, "maxDrawdown": maxDD}


def _parseLastCycleFromLog(logPath: str = "logs/bot.log") -> str:
    """Scan bot.log tail for last cycle timestamp. Return 'No log yet' if absent."""
    lines = summarizeRecentLogs(logPath, lines=100)
    if not lines:
        return "No log yet"
    for line in reversed(lines.splitlines()):
        if "runCycle" in line or "cycle" in line.lower():
            return line[:40]
    return "Unknown"
