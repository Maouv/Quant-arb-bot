"""Monitor open positions and dispatch exit signals."""

import logging
from typing import Any

from src.config.settings import MIN_SPOT_NOTIONAL
from src.execution.exit_handler import exitEmergency, exitNormal
from src.position.balance import fetchSpotBalance
from src.strategy.signal import isExitSignal, isFundingRateFlipped

logger = logging.getLogger(__name__)


def monitorPositions(
    openPositions: list[dict[str, Any]],
    premiumIndex: list[dict[str, Any]],
    botState: dict[str, object],
) -> None:
    """Check each open position for exit signals. FR flip → emergency. FR < threshold → normal."""
    frMap = {p["symbol"]: float(p.get("lastFundingRate") or 0) * 100 for p in premiumIndex}
    for pos in openPositions:
        symbol = str(pos.get("symbol", ""))
        currentFr = frMap.get(symbol, 0.0)
        entryFr = float(str(pos.get("entryFr", currentFr)))
        markPrice = float(str(pos.get("markPrice", 1.0)))
        futQty = float(pos.get("positionAmt") or 0)
        spotQty = _resolveSpotQty(botState["spotExchange"], symbol, markPrice)
        kwargs: dict[str, object] = {
            "spotExchange": botState["spotExchange"],
            "futuresExchange": botState["futuresExchange"],
            "symbol": symbol, "spotSide": "sell", "futuresSide": "buy",
            "spotQuantity": spotQty, "futuresQuantity": futQty,
            "algoIds": [], "baseUrl": str(botState["baseUrl"]),
            "apiKey": str(botState["apiKey"]), "apiSecret": str(botState["apiSecret"]),
        }
        try:
            if isFundingRateFlipped(entryFr, currentFr):
                exitEmergency(**kwargs)  # type: ignore[arg-type]
            elif isExitSignal(currentFr):
                exitNormal(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            logger.error("Exit failed for %s: %s", symbol, exc)


def _resolveSpotQty(spotExchange: object, symbol: str, markPrice: float) -> float:
    """Fetch actual spot balance. Return 0.0 if below MIN_SPOT_NOTIONAL (dust)."""
    baseAsset = symbol.replace("USDT", "")
    bal = fetchSpotBalance(spotExchange, baseAsset)
    if bal * markPrice < MIN_SPOT_NOTIONAL:
        logger.warning("monitor %s: spotBal=%.4f below dust threshold, skip spot leg", symbol, bal)
        return 0.0
    return bal
