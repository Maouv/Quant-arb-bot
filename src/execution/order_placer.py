"""Place spot + futures limit orders simultaneously."""

import logging

from src.config.settings import MIN_NOTIONAL_FUTURES

logger = logging.getLogger(__name__)


def calculateQuantity(
    markPrice: float, sizePerPair: float, minNotional: float = MIN_NOTIONAL_FUTURES,
) -> float:
    """
    quantity = sizePerPair / markPrice.
    Raise ValueError kalau notional < minNotional ($50 futures).
    """
    if markPrice <= 0:
        raise ValueError(f"markPrice must be positive, got {markPrice}")
    quantity = sizePerPair / markPrice
    if quantity * markPrice < minNotional:
        raise ValueError(f"Notional {quantity * markPrice:.2f} below minimum {minNotional}")
    return quantity


def placeEntryOrders(
    spotExchange: object, futuresExchange: object, symbol: str,
    spotSide: str, futuresSide: str, quantity: float,
    spotPrice: float, futuresPrice: float,
) -> tuple[dict[str, object], dict[str, object]]:
    """
    Place spot + futures LIMIT order bersamaan (mid price). timeInForce: GTC.
    Return: (spotOrder, futuresOrder) — raw order dicts. Caller handles fill monitoring.
    """
    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    logger.info(
        "Placing entry orders: %s spot=%s futures=%s qty=%s",
        symbol, spotSide, futuresSide, quantity,
    )
    spotOrder: dict[str, object] = spotExchange.create_order(  # type: ignore[attr-defined]
        symbol=spotSymbol, type="limit", side=spotSide.lower(),
        amount=quantity, price=spotPrice, params={"timeInForce": "GTC"},
    )
    futuresOrder: dict[str, object] = futuresExchange.create_order(  # type: ignore[attr-defined]
        symbol=futSymbol, type="limit", side=futuresSide.lower(),
        amount=quantity, price=futuresPrice, params={"timeInForce": "GTC"},
    )
    logger.info(
        "Entry orders placed: spotId=%s futuresId=%s", spotOrder.get("id"), futuresOrder.get("id")
    )
    return spotOrder, futuresOrder
