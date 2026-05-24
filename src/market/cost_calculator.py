"""Cost calculations for spread, basis, and net expected profit."""

from src.config.settings import FEE_RT, TAKER_FEE


def calculateSpread(bid: float, ask: float) -> float:
    """(ask - bid) / midPrice * 100 — dalam %."""
    midPrice = (bid + ask) / 2
    if midPrice == 0:
        return 0.0
    return (ask - bid) / midPrice * 100


def calculateBasis(markPrice: float, indexPrice: float) -> float:
    """|markPrice - indexPrice| / indexPrice * 100 — dalam %."""
    if indexPrice == 0:
        return 0.0
    return abs(markPrice - indexPrice) / indexPrice * 100


def calculateTotalRtCost(spreadSpot: float, spreadFutures: float, slippageSpot: float,
                         slippageFutures: float, basis: float) -> float:
    """
    total_rt_cost = FEE_RT + (spreadSpot * 2) + (spreadFutures * 2)
                  + (slippageSpot * 2) + (slippageFutures * 2) + basis.
    Semua dalam %.
    """
    return (FEE_RT + (spreadSpot * 2) + (spreadFutures * 2)
            + (slippageSpot * 2) + (slippageFutures * 2) + basis)


def calculateNetExpected(fundingRate: float, totalRtCost: float) -> float:
    """net_expected = |fundingRate * 100| - totalRtCost."""
    return abs(fundingRate * 100) - totalRtCost


def calculateActualCostRt(fillPriceSpot: float, midPriceSpot: float,
                          fillPriceFutures: float, midPriceFutures: float) -> float:
    """
    Post-trade actual cost:
    = (|fillSpot - midSpot| / midSpot + |fillFutures - midFutures| / midFutures
     + TAKER_FEE * 4) * 100.
    """
    costSpot = abs(fillPriceSpot - midPriceSpot) / midPriceSpot if midPriceSpot > 0 else 0.0
    costFutures = (abs(fillPriceFutures - midPriceFutures) / midPriceFutures
                   if midPriceFutures > 0 else 0.0)
    return (costSpot + costFutures + TAKER_FEE * 4) * 100
