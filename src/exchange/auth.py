"""HMAC-SHA256 signed request for raw API calls."""

import hashlib
import hmac
import time

import requests


def signedRequest(
    method: str,
    baseUrl: str,
    endpoint: str,
    params: dict[str, str | int],
    apiKey: str,
    apiSecret: str,
) -> dict[str, str | int | float]:
    """
    HMAC-SHA256 signed request untuk raw API calls.
    Dipakai oleh algo_order.py (ccxt tidak support algo endpoint).

    Steps:
    1. Tambah timestamp ke params
    2. Build query string
    3. Sign dengan HMAC-SHA256
    4. Send request dengan X-MBX-APIKEY header
    5. Raise on HTTP error
    6. Return parsed JSON
    """
    params["timestamp"] = int(time.time() * 1000)
    queryString = "&".join(f"{k}={v}" for k, v in params.items())
    signature = hmac.new(
        apiSecret.encode(), queryString.encode(), hashlib.sha256
    ).hexdigest()

    url = f"{baseUrl}{endpoint}"
    headers = {"X-MBX-APIKEY": apiKey}

    if method == "GET":
        response = requests.get(
            url, params=params | {"signature": signature}, headers=headers, timeout=30
        )
    elif method == "POST":
        response = requests.post(
            url, params=params | {"signature": signature}, headers=headers, timeout=30
        )
    elif method == "DELETE":
        response = requests.delete(
            url, params=params | {"signature": signature}, headers=headers, timeout=30
        )
    else:
        raise ValueError(f"Unsupported method: {method}")

    response.raise_for_status()
    result: dict[str, str | int | float] = response.json()
    return result
