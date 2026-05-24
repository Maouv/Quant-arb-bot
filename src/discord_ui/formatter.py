"""Discord embed formatters for bot state output."""

import discord


def formatPositionsEmbed(positions: list[dict[str, object]]) -> discord.Embed:
    """Format positions ke Discord embed. Source: raw ccxt pos["info"]."""
    embed = discord.Embed(title="📊 Open Positions", color=discord.Color.blue())
    if not positions:
        embed.description = "No open positions."
        return embed
    for pos in positions:
        info: dict[str, str] = pos.get("info", {})  # type: ignore[assignment]
        symbol = info.get("symbol", "?")
        amt = float(info.get("positionAmt", "0"))
        side = "LONG" if amt > 0 else "SHORT"
        entry = info.get("entryPrice", "?")
        mark = info.get("markPrice", "?")
        pnl = info.get("unRealizedProfit", "?")
        embed.add_field(
            name=f"{symbol} [{side}]",
            value=f"Entry: `{entry}` | Mark: `{mark}` | PnL: `{pnl}`",
            inline=False,
        )
    return embed


def formatMetricsEmbed(metrics: dict[str, object]) -> discord.Embed:
    """Format metrics summary ke Discord embed."""
    embed = discord.Embed(title="📈 Performance Metrics", color=discord.Color.green())
    fields: list[tuple[str, str]] = [
        ("Total Net $", f"`${metrics.get('totalNetDollar', 0):.2f}`"),
        ("Trade Count", f"`{metrics.get('tradeCount', 0)}`"),
        ("Win / Loss", f"`{metrics.get('wins', 0)} / {metrics.get('losses', 0)}`"),
        ("Avg Cost (RT)", f"`{metrics.get('avgCostRtPct', 0):.4f}%`"),
        ("Fill Rate", f"`{metrics.get('fillRate', 0):.1f}%`"),
        ("Max Drawdown", f"`${metrics.get('maxDrawdown', 0):.2f}`"),
    ]
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=True)
    return embed


def formatTradesEmbed(trades: list[dict[str, object]]) -> discord.Embed:
    """Format recent trades ke Discord embed."""
    embed = discord.Embed(title="📋 Recent Trades", color=discord.Color.orange())
    if not trades:
        embed.description = "No trades recorded."
        return embed
    for trade in trades:
        symbol = trade.get("symbol", "?")
        net = trade.get("net_dollar", 0)
        entry_fr = trade.get("entry_fr", 0)
        embed.add_field(
            name=f"{symbol}",
            value=f"Net: `${net:.2f}` | FR: `{entry_fr:.4f}%`",
            inline=False,
        )
    return embed


def formatStatusEmbed(status: dict[str, object]) -> discord.Embed:
    """Format bot status ke Discord embed."""
    embed = discord.Embed(title="🤖 Bot Status", color=discord.Color.purple())
    fields: list[tuple[str, str]] = [
        ("Balance", f"`${status.get('balance', 'N/A')}`"),
        ("Open Positions", f"`{status.get('openPositions', 0)}`"),
        ("Last Cycle", f"`{status.get('lastCycle', 'Unknown')}`"),
        ("Uptime", f"`{status.get('uptime', 'Unknown')}`"),
    ]
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=True)
    return embed
