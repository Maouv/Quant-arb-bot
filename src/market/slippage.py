"""Slippage estimation from order book depth."""

import logging

logger = logging.getLogger(__name__)

type OrderBookLevel = list[str]


def estimateSlippage(asks: list[OrderBookLevel], bids: list[OrderBookLevel],
                     positionSize: float) -> float:
    """
    Scan asks, accumulate notional sampai positionSize terpenuhi.
    Return slippage % = (worstFillPrice - midPrice) / midPrice * 100.

    midPrice = (bestBid + bestAsk) / 2
    """
    if not asks or not bids:
        logger.warning("Empty order book")
        return 0.0

    bestBid = float(bids[0][0])
    bestAsk = float(asks[0][0])
    midPrice = (bestBid + bestAsk) / 2

    if midPrice == 0:
        return 0.0

    accumulated = 0.0
    worstPrice = bestAsk

    for priceStr, qtyStr in asks:
        price = float(priceStr)
        qty = float(qtyStr)
        notional = price * qty
        accumulated += notional
        worstPrice = price
        if accumulated >= positionSize:
            break

    return (worstPrice - midPrice) / midPrice * 100
