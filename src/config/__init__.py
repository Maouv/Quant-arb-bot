"""Configuration package."""

from src.config.secrets import loadSecrets
from src.config.settings import *
from src.config.universe import UNIVERSE_8H

__all__ = ["loadSecrets", "UNIVERSE_8H"]
