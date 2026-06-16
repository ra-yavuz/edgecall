"""Current gold spot price, from a public no-key API.

Calls gold-api.com, which returns the current XAU (gold, troy ounce) spot
price in USD with no API key. A template for "hit a public REST endpoint
and reshape the JSON".
"""

from __future__ import annotations

from typing import Any, Dict

import httpx

from edgecall.registry import register

_URL = "https://api.gold-api.com/price/XAU"


@register(id="0002", desc="find the current gold price")
def run(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = httpx.get(_URL, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"gold price lookup failed: {exc}"}
    except ValueError as exc:
        return {"error": f"gold price API returned non-JSON: {exc}"}

    return {
        "metal": data.get("name", "Gold"),
        "symbol": data.get("symbol", "XAU"),
        "price": data.get("price"),
        "currency": data.get("currency", "USD"),
        "unit": "troy ounce",
        "updated_at": data.get("updatedAt"),
        "source": _URL,
    }
