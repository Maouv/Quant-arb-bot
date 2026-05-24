"""
Discord UI tests — formatter output + command auth logic.
Pure unit tests, no live Discord connection required.
"""

import discord
import pytest

from src.discord_ui.formatter import (
    formatMetricsEmbed,
    formatPositionsEmbed,
    formatStatusEmbed,
    formatTradesEmbed,
)

# ── Formatter tests ────────────────────────────────────────────────────────────

def _makeRawPosition(symbol: str, amt: str = "1.0") -> dict[str, object]:
    """Build raw ccxt-style position dict with info nested."""
    return {"info": {"symbol": symbol, "positionAmt": amt,
                     "entryPrice": "90000.00", "markPrice": "91000.00",
                     "unRealizedProfit": "100.00"}}


def test_formatPositionsEmbed_empty() -> None:
    """Empty positions → embed with 'No open positions.' description."""
    embed = formatPositionsEmbed([])
    assert isinstance(embed, discord.Embed)
    assert embed.description == "No open positions."
    assert len(embed.fields) == 0


def test_formatPositionsEmbed_single_long() -> None:
    """Single long position → 1 field, title contains symbol + LONG."""
    embed = formatPositionsEmbed([_makeRawPosition("BTCUSDT", "1.0")])
    assert len(embed.fields) == 1
    fieldName = embed.fields[0].name or ""
    assert "BTCUSDT" in fieldName
    assert "LONG" in fieldName


def test_formatPositionsEmbed_single_short() -> None:
    """Negative positionAmt → SHORT label."""
    embed = formatPositionsEmbed([_makeRawPosition("ETHUSDT", "-1.0")])
    fieldName = embed.fields[0].name or ""
    assert "SHORT" in fieldName


def test_formatPositionsEmbed_multiple() -> None:
    """Multiple positions → correct field count."""
    positions = [_makeRawPosition("BTCUSDT"), _makeRawPosition("ETHUSDT")]
    embed = formatPositionsEmbed(positions)
    assert len(embed.fields) == 2


def test_formatMetricsEmbed_fields() -> None:
    """Metrics embed has all 6 expected fields."""
    metrics: dict[str, object] = {
        "totalNetDollar": 150.0, "tradeCount": 10,
        "wins": 7, "losses": 3, "avgCostRtPct": 0.12,
        "fillRate": 70.0, "maxDrawdown": 25.0,
    }
    embed = formatMetricsEmbed(metrics)
    assert isinstance(embed, discord.Embed)
    assert len(embed.fields) == 6
    field_names = [f.name or "" for f in embed.fields]
    assert "Total Net $" in field_names
    assert "Fill Rate" in field_names


def test_formatMetricsEmbed_zero_values() -> None:
    """Empty metrics → no crash, all fields present."""
    embed = formatMetricsEmbed({})
    assert len(embed.fields) == 6


def test_formatTradesEmbed_empty() -> None:
    """Empty trades → 'No trades recorded.' description."""
    embed = formatTradesEmbed([])
    assert embed.description == "No trades recorded."
    assert len(embed.fields) == 0


def test_formatTradesEmbed_entries() -> None:
    """Trade entries → correct field count."""
    trades: list[dict[str, object]] = [
        {"symbol": "BTCUSDT", "net_dollar": 25.0, "entry_fr": 0.05},
        {"symbol": "ETHUSDT", "net_dollar": -5.0, "entry_fr": 0.06},
    ]
    embed = formatTradesEmbed(trades)
    assert len(embed.fields) == 2
    assert (embed.fields[0].name or "") == "BTCUSDT"


def test_formatStatusEmbed_fields() -> None:
    """Status embed has 4 fields: Balance, Open Positions, Last Cycle, Uptime."""
    status: dict[str, object] = {
        "balance": "1500.00", "openPositions": 3,
        "lastCycle": "2026-05-24T10:00:00Z", "uptime": "2h 30m",
    }
    embed = formatStatusEmbed(status)
    assert isinstance(embed, discord.Embed)
    assert len(embed.fields) == 4
    field_names = [f.name or "" for f in embed.fields]
    assert "Balance" in field_names
    assert "Last Cycle" in field_names


def test_formatStatusEmbed_empty() -> None:
    """Empty status dict → no crash, fallback values used."""
    embed = formatStatusEmbed({})
    assert len(embed.fields) == 4


# ── Command auth logic tests ───────────────────────────────────────────────────

def test_computeMetrics_empty_trades() -> None:
    """_computeMetrics with empty list → all zeros, no crash."""
    from src.discord_ui.commands import _computeMetrics
    result = _computeMetrics([])
    assert result["tradeCount"] == 0
    assert result["totalNetDollar"] == 0.0
    assert result["maxDrawdown"] == 0.0


def test_computeMetrics_all_wins() -> None:
    """All positive net trades → 100% fill rate, wins == tradeCount."""
    from src.discord_ui.commands import _computeMetrics
    trades: list[dict[str, object]] = [
        {"net_dollar": 10.0, "cost_rt_pct": 0.12},
        {"net_dollar": 20.0, "cost_rt_pct": 0.10},
    ]
    result = _computeMetrics(trades)
    assert result["wins"] == 2
    assert result["losses"] == 0
    assert result["fillRate"] == pytest.approx(100.0)


def test_computeMetrics_max_drawdown() -> None:
    """Peak then loss → drawdown correctly computed."""
    from src.discord_ui.commands import _computeMetrics
    trades: list[dict[str, object]] = [
        {"net_dollar": 100.0, "cost_rt_pct": 0.1},
        {"net_dollar": -40.0, "cost_rt_pct": 0.1},
    ]
    result = _computeMetrics(trades)
    assert result["maxDrawdown"] == pytest.approx(40.0)


def test_parseLastCycleFromLog_no_file(tmp_path: pytest.TempPathFactory) -> None:
    """Non-existent log path → 'No log yet'."""
    from src.discord_ui.commands import _parseLastCycleFromLog
    result = _parseLastCycleFromLog(str(tmp_path) + "/missing.log")
    assert result == "No log yet"
