"""Current weather for a coordinate, from open-meteo (no key).

open-meteo serves current conditions for any latitude/longitude with no API
key. This function reads optional ``latitude``/``longitude`` from the
request args and falls back to a default city, showing how a function can
take structured args alongside the natural-language request.
"""

from __future__ import annotations

from typing import Any, Dict

import httpx

from edgecall.registry import register

_URL = "https://api.open-meteo.com/v1/forecast"
# Default location when the caller passes no coordinates: Berlin.
_DEFAULT_LAT = 52.52
_DEFAULT_LON = 13.41


@register(id="0003", desc="get the current weather for a location")
def run(args: Dict[str, Any]) -> Dict[str, Any]:
    lat = args.get("latitude", _DEFAULT_LAT)
    lon = args.get("longitude", _DEFAULT_LON)
    try:
        resp = httpx.get(
            _URL,
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"weather lookup failed: {exc}"}
    except ValueError as exc:
        return {"error": f"weather API returned non-JSON: {exc}"}

    cur = data.get("current_weather", {})
    return {
        "latitude": data.get("latitude", lat),
        "longitude": data.get("longitude", lon),
        "temperature_c": cur.get("temperature"),
        "windspeed_kmh": cur.get("windspeed"),
        "weathercode": cur.get("weathercode"),
        "time": cur.get("time"),
        "source": _URL,
    }
