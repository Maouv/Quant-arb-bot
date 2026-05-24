"""Monitor open positions and dispatch exit signals."""

import logging
from typing import Any

from src.execution.exit_handler import exitEmergency, exitNormal
from src.strategy.signal import isExitSignal, isFundingRateFlipped

logger = logging.getLogger(__name__)


def monitorPositions(
    openPositions: list[dict[str, Any]],
    premiumIndex: list[dict[str, Any]],
    botState: dict[str, object],
) -> None:
    """
    Check each open position for exit signals.
    FR flip → exitEmergency. FR < EXIT_THRESHOLD → exitNormal.
    """
    frMap = {p["symbol"]: float(p["lastFundingRate"]) * 100 for p in premiumIndex}
    for pos in openPositions:
        symbol = str(pos.get("symbol", ""))
        currentFr = frMap.get(symbol, 0.0)
        entryFr = float(str(pos.get("entryFr", currentFr)))
        kwargs: dict[str, object] = {
            "spotExchange": botState["spotExchange"],
            "futuresExchange": botState["futuresExchange"],
            "symbol": symbol, "spotSide": "sell", "futuresSide": "buy",
            "quantity": float(str(pos.get("positionAmt", 0))),
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
