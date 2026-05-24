"""Load secrets from ~/.secrets/quant-arb-bot/.env"""

import os
from pathlib import Path

from dotenv import load_dotenv


def loadSecrets() -> dict[str, str]:
    """
    Load .env dari ~/.secrets/quant-arb-bot/.env
    Return dict: {key_name: value}
    Raise RuntimeError jika file tidak ada.
    """
    secretsPath = Path.home() / ".secrets" / "quant-arb-bot" / ".env"

    if not secretsPath.exists():
        raise RuntimeError(
            f"Secrets file not found: {secretsPath}\n"
            "Run: mkdir -p ~/.secrets/quant-arb-bot && "
            "cp .env.example ~/.secrets/quant-arb-bot/.env"
        )

    load_dotenv(secretsPath)

    secrets: dict[str, str] = {}
    for key in [
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BINANCE_TESTNET_KEY",
        "BINANCE_TESTNET_SECRET",
        "BINANCE_TESTNET_SPOT_KEY",
        "BINANCE_TESTNET_SPOT_SECRET",
    ]:
        value = os.getenv(key)
        if value:
            secrets[key] = value

    return secrets
