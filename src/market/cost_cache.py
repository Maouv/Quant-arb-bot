"""Rolling average cost per coin persistence."""

import json
import logging
from pathlib import Path

from src.config.settings import DEFAULT_COST_TIER

logger = logging.getLogger(__name__)


class CostCache:
    """Rolling average cost per coin. Persist ke logs/cost_cache.json."""

    def __init__(self, filepath: str = "logs/cost_cache.json"):
        self.filepath = filepath
        self.data: dict[str, list[float]] = {}
        self.load()

    def update(self, symbol: str, cost: float) -> None:
        """Tambah data point, recompute rolling avg."""
        if symbol not in self.data:
            self.data[symbol] = []
        self.data[symbol].append(cost)
        if len(self.data[symbol]) > 100:
            self.data[symbol] = self.data[symbol][-100:]

    def getRollingAvg(self, symbol: str) -> float:
        """Return rolling avg. Fallback: DEFAULT_COST_TIER."""
        if symbol not in self.data or not self.data[symbol]:
            return DEFAULT_COST_TIER
        return sum(self.data[symbol]) / len(self.data[symbol])

    def save(self) -> None:
        """Write ke disk."""
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=2)
        logger.debug(f"Cost cache saved to {self.filepath}")

    def load(self) -> None:
        """Load dari disk. No-op kalau file belum ada."""
        if not Path(self.filepath).exists():
            logger.debug(f"Cost cache file not found: {self.filepath}")
            return
        with open(self.filepath) as f:
            self.data = json.load(f)
        logger.debug(f"Cost cache loaded from {self.filepath}")
