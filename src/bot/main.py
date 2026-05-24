"""Bot entrypoint. Run: python -m src.bot.main"""

import logging

from src.bot.cycle import runCycle
from src.bot.startup import runStartupSequence, waitForNextCycle
from src.logging_.setup import configureLogging
from src.market.cost_cache import CostCache

logger = logging.getLogger(__name__)


def main() -> None:
    """
    1. configureLogging()  2. runStartupSequence()
    3. Loop: runCycle() → waitForNextCycle()
    Ctrl+C → graceful shutdown (log + save cost cache).
    """
    configureLogging()
    logger.info("Bot starting")
    botState = runStartupSequence()
    try:
        while True:
            runCycle(botState)
            waitForNextCycle()
    except KeyboardInterrupt:
        logger.info("Shutdown requested — saving state")
        costCache = botState.get("costCache")
        if isinstance(costCache, CostCache):
            costCache.save()
        logger.info("Bot stopped cleanly")


if __name__ == "__main__":
    main()
