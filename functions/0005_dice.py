"""Roll dice. A tiny function that takes an optional structured arg.

Reads ``sides`` from the request args (default 6). Also on menu page 2,
reinforcing that less-used functions belong later in the registry.
"""

from __future__ import annotations

import secrets
from typing import Any, Dict

from edgecall.registry import register


@register(id="0005", desc="roll a die and return the result")
def run(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sides = int(args.get("sides", 6))
    except (TypeError, ValueError):
        return {"error": "sides must be an integer"}
    if sides < 2:
        return {"error": "a die needs at least 2 sides"}
    return {"sides": sides, "roll": secrets.randbelow(sides) + 1}
