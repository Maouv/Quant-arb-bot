"""Build AI message context from botState snapshot + query."""

import logging
from pathlib import Path

from src.config import settings
from src.market.cost_cache import CostCache

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


def buildContext(botState: dict[str, object], query: str) -> list[dict[str, str]]:
    """
    Build messages array untuk AI:
    1. System prompt (dari ai/prompts/system.md)
    2. Context data (positions, trades, status, cost cache, logs)
    3. User query
    Return: [{"role": "system", ...}, {"role": "user", ...}]
    """
    systemPrompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    contextParts: list[str] = []

    positions: list[dict[str, object]] = botState.get("openPositions", [])  # type: ignore[assignment]
    trades: list[dict[str, object]] = botState.get("trades", [])  # type: ignore[assignment]
    costCache: CostCache | None = botState.get("costCache")  # type: ignore[assignment]
    logPath: str = botState.get("logPath", "logs/bot.log")  # type: ignore[assignment]
    balance: float | None = botState.get("availableBalance")  # type: ignore[assignment]

    if positions:
        contextParts.append(f"## Open Positions\n{summarizePositions(positions)}")
    if balance is not None:
        contextParts.append(f"## Available Balance\n${balance:.2f} USDT")
    if trades:
        contextParts.append(f"## Recent Trades\n{summarizeMetrics(trades)}")
    if costCache is not None:
        contextParts.append(f"## Cost Cache\n{summarizeCostCache(costCache)}")

    logSummary = summarizeRecentLogs(str(logPath))
    if logSummary:
        contextParts.append(f"## Recent Logs\n{logSummary}")

    contextBlock = "\n\n".join(contextParts) if contextParts else "No data available."
    userMessage = f"Context:\n{contextBlock}\n\nQuestion: {query}"
    return [{"role": "system", "content": systemPrompt}, {"role": "user", "content": userMessage}]


def summarizePositions(positions: list[dict[str, object]]) -> str:
    """Compact text summary of open positions."""
    lines: list[str] = []
    for pos in positions:
        info: dict[str, str] = pos.get("info", {})  # type: ignore[assignment]
        symbol = info.get("symbol", "?")
        side = "LONG" if float(info.get("positionAmt", "0")) > 0 else "SHORT"
        entry = info.get("entryPrice", "?")
        pnl = info.get("unRealizedProfit", "?")
        lines.append(f"  {symbol} {side} entry={entry} pnl={pnl}")
    return "\n".join(lines) if lines else "No open positions."


def summarizeMetrics(trades: list[dict[str, object]]) -> str:
    """Compact text summary of performance metrics from recent trades."""
    recent = trades[-settings.AI_RECENT_TRADES_FOR_CONTEXT:]
    netDollars = [float(t.get("net_dollar", 0)) for t in recent]  # type: ignore[arg-type]
    totalNet = sum(netDollars)
    wins = sum(1 for n in netDollars if n > 0)
    losses = len(netDollars) - wins
    return (
        f"  Last {len(recent)} trades | net=${totalNet:.2f} | "
        f"wins={wins} losses={losses} | total_trades={len(trades)}"
    )


def summarizeRecentLogs(logPath: str, lines: int = 50) -> str:
    """Last N lines dari bot.log. Return empty string kalau file tidak ada."""
    path = Path(logPath)
    if not path.exists():
        logger.debug("Log file not found: %s", logPath)
        return ""
    allLines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(allLines[-lines:])


def summarizeCostCache(costCache: CostCache) -> str:
    """Top coins by cost, avg cost across universe."""
    if not costCache.data:
        return "No cost data available."
    avgs = {sym: sum(v) / len(v) for sym, v in costCache.data.items() if v}
    topCoins = sorted(avgs.items(), key=lambda x: x[1], reverse=True)[:settings.AI_TOP_COST_COINS]
    lines = [f"  {sym}: {avg:.4f}%" for sym, avg in topCoins]
    overallAvg = sum(avgs.values()) / len(avgs) if avgs else 0.0
    lines.append(f"  overall_avg={overallAvg:.4f}%")
    return "\n".join(lines)
