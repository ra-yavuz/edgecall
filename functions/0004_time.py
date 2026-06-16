"""Current UTC time. A no-network function with zero dependencies.

Lands on menu page 2 (with default page size 3), so it is the first example
a weak model can only reach by replying NEXT once: handy for seeing
pagination work end to end.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from edgecall.registry import register


@register(id="0004", desc="tell the current date and time (UTC)")
def run(args: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(timespec="seconds"),
        "weekday": now.strftime("%A"),
    }
