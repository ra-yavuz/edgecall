"""Pagination and prompt-as-menu logic.

The whole point of edgecall is that a deliberately weak model only ever has
to do the easiest possible thing: pick one option from a short menu. This
module turns a page of the registry into a menu the model reads, and turns
the model's short text reply back into a decision.

Decision flow, one model turn at a time:

  page 0 ->  0001  find the current gold price
             0002  show the message of the day
             NEXT  see more options
  model replies "NEXT"  -> show page 1
  model replies "0001"  -> run function 0001
  model replies garbage -> we re-ask (caller decides how many times)

There is intentionally NO retrieval and NO embedding here. Pages are slices
of the registry in registration order. The trade-off, documented for users:
a function deep in the registry costs the model one "NEXT" per page to
reach, and weak models page blindly, so put common functions first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .registry import Function, Registry

# How many functions to show per page. Kept small on purpose: a weak model
# reasons better over fewer options. 3 leaves room for the NEXT control
# without crowding the menu.
DEFAULT_PAGE_SIZE = 3

NEXT_TOKEN = "NEXT"


@dataclass(frozen=True)
class Page:
    """One menu page: a slice of functions plus whether more follow."""

    index: int
    functions: List[Function]
    has_next: bool
    total_pages: int


@dataclass(frozen=True)
class Decision:
    """The parsed outcome of one model reply."""

    kind: str  # "pick" | "next" | "unparseable"
    function: Optional[Function] = None  # set when kind == "pick"


def paginate(registry: Registry, page_index: int, page_size: int = DEFAULT_PAGE_SIZE) -> Page:
    """Return the page at ``page_index`` (0-based)."""
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    funcs = registry.all()
    total = len(funcs)
    total_pages = max(1, (total + page_size - 1) // page_size)
    # Clamp so an out-of-range index from a confused model lands on the last
    # page rather than an empty one.
    idx = max(0, min(page_index, total_pages - 1))
    start = idx * page_size
    chunk = funcs[start : start + page_size]
    has_next = (start + page_size) < total
    return Page(index=idx, functions=chunk, has_next=has_next, total_pages=total_pages)


def render_menu(request: str, page: Page) -> str:
    """Build the prompt the weak model sees for one decision.

    The instruction is deliberately blunt and repeated, because weak models
    drift: we tell them to reply with only an id, we list the exact ids, and
    we give one escape (NEXT) and one example shape.
    """
    lines: List[str] = []
    lines.append("You route a user request to ONE action by its id.")
    lines.append(f'User request: "{request.strip()}"')
    lines.append("")
    lines.append("Options:")
    for fn in page.functions:
        lines.append(f"  {fn.id}  {fn.desc}")
    if page.has_next:
        lines.append(f"  {NEXT_TOKEN}  none of these, see more options")
    lines.append("")
    valid = [fn.id for fn in page.functions]
    if page.has_next:
        valid.append(NEXT_TOKEN)
    lines.append(
        "Reply with EXACTLY ONE id from the list above and nothing else. "
        f"Valid replies: {', '.join(valid)}."
    )
    return "\n".join(lines)


def parse_reply(reply: str, page: Page) -> Decision:
    """Interpret a model's text reply against the page it was shown.

    We are lenient about surrounding noise (a weak model may answer
    "The answer is 0001.") but strict about which token we accept: only an
    id that was actually on this page, or NEXT when this page offered it.
    Anything else is unparseable, and the caller decides whether to re-ask.
    """
    text = (reply or "").strip()
    if not text:
        return Decision(kind="unparseable")

    # NEXT first: only honoured when the page actually offered it, so a
    # model saying NEXT on the last page does not loop forever.
    if page.has_next and re.search(rf"\b{NEXT_TOKEN}\b", text, re.IGNORECASE):
        # Guard: if the reply also clearly names a function id on this page,
        # prefer the concrete pick over NEXT.
        for fn in page.functions:
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(fn.id)}(?![A-Za-z0-9_-])", text):
                return Decision(kind="pick", function=fn)
        return Decision(kind="next")

    # Look for exactly one id from this page as a whole token.
    matched: List[Function] = []
    for fn in page.functions:
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(fn.id)}(?![A-Za-z0-9_-])", text):
            matched.append(fn)
    if len(matched) == 1:
        return Decision(kind="pick", function=matched[0])

    # Zero matches, or an ambiguous reply naming several ids: do not guess.
    return Decision(kind="unparseable")
