"""Message-of-the-day function: serve text from a file.

The simplest possible edgecall function and a useful template: no network,
just read a file and return it. The file path comes from the EDGECALL_MOTD
environment variable, falling back to motd.txt sitting next to this file.

Register order note: this is 0001 so it lands on the first menu page; a
weak model reaches it without paging.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from edgecall.registry import register

_DEFAULT_MOTD = Path(__file__).resolve().parent / "motd.txt"


@register(id="0001", desc="show the message of the day")
def run(args: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(os.environ.get("EDGECALL_MOTD") or _DEFAULT_MOTD)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        # Returning an error dict (not raising) lets the caller see what
        # went wrong without the whole dispatch being marked a crash.
        return {"error": f"could not read motd file {path}: {exc}"}
    return {"message": text, "source": str(path)}
