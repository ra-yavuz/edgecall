"""Function registry for edgecall.

A function is the unit a weak model can choose to run. Each one has:

  - an id   : a short stable string like "0001" the model emits to pick it
  - a desc  : a one-line natural-language description the model reads
  - a run() : the Python callable that does the work

Authors register functions by decorating a callable with @register in a
file under the functions/ directory. The loader (see loader.py) imports
every such file at startup, which runs the decorators, which fills this
registry. Nothing here selects or paginates; that is the menu engine's
job. This module only stores and validates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# A function id is intentionally restrictive: short, no spaces, so a weak
# model can echo it back verbatim and we can match it without ambiguity.
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")

# "NEXT" is reserved: it is the pagination control the menu engine injects,
# so a function may not claim it as an id.
_RESERVED_IDS = {"NEXT"}


@dataclass(frozen=True)
class Function:
    """One registered, callable function."""

    id: str
    desc: str
    run: Callable[[Dict[str, Any]], Any]
    # Free-form extra metadata an author may attach (unused by the core,
    # available to anyone who wants to extend behaviour later).
    meta: Dict[str, Any]


class RegistryError(ValueError):
    """Raised when a registration is invalid (bad id, duplicate, etc.)."""


class Registry:
    """An ordered collection of functions.

    Order matters: pagination walks the registry in registration order, so
    the order files are loaded and decorators run is the order the model
    pages through. Most-used functions should be registered first.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Function] = {}
        self._order: List[str] = []

    def add(
        self,
        *,
        id: str,
        desc: str,
        run: Callable[[Dict[str, Any]], Any],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Function:
        fid = str(id).strip()
        if not _ID_RE.match(fid):
            raise RegistryError(
                f"invalid function id {id!r}: must match {_ID_RE.pattern}"
            )
        if fid.upper() in _RESERVED_IDS:
            raise RegistryError(f"function id {fid!r} is reserved")
        if fid in self._by_id:
            raise RegistryError(f"duplicate function id {fid!r}")

        desc = str(desc).strip()
        if not desc:
            raise RegistryError(f"function {fid!r} has an empty description")
        # The description is shown to the model on a single menu line, so a
        # newline would break the menu format. Reject it loudly rather than
        # silently mangling it.
        if "\n" in desc:
            raise RegistryError(
                f"function {fid!r} description must be a single line"
            )
        if not callable(run):
            raise RegistryError(f"function {fid!r} run target is not callable")

        fn = Function(id=fid, desc=desc, run=run, meta=dict(meta or {}))
        self._by_id[fid] = fn
        self._order.append(fid)
        return fn

    def get(self, fid: str) -> Optional[Function]:
        return self._by_id.get(str(fid).strip())

    def all(self) -> List[Function]:
        """Functions in registration order (the order pagination uses)."""
        return [self._by_id[i] for i in self._order]

    def __len__(self) -> int:
        return len(self._order)


# The process-wide registry the @register decorator writes into and the
# loader/menu engine read from.
REGISTRY = Registry()


def register(
    *,
    id: str,
    desc: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Callable[[Callable[[Dict[str, Any]], Any]], Callable[[Dict[str, Any]], Any]]:
    """Decorator that adds the wrapped callable to the global registry.

    Usage in a functions/ file::

        from edgecall.registry import register

        @register(id="0001", desc="find the current gold price")
        def run(args):
            ...
            return {"price_usd_per_oz": 2400}

    The wrapped callable receives a single dict ``args`` (the request
    payload) and returns any JSON-serialisable value, which edgecall sends
    back to the API caller.
    """

    def deco(fn: Callable[[Dict[str, Any]], Any]) -> Callable[[Dict[str, Any]], Any]:
        REGISTRY.add(id=id, desc=desc, run=fn, meta=meta)
        return fn

    return deco
