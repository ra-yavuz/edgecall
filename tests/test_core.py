"""Core logic tests: registry, pagination, reply parsing, dispatch loop.

These run with no live model: a FakeClient returns scripted replies so we
can assert the dispatcher's behaviour deterministically.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the package importable from the repo without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from edgecall.dispatcher import Dispatcher  # noqa: E402
from edgecall.menu import NEXT_TOKEN, paginate, parse_reply, render_menu  # noqa: E402
from edgecall.registry import Registry, RegistryError  # noqa: E402


def make_registry(n: int) -> Registry:
    r = Registry()
    for i in range(1, n + 1):
        fid = f"{i:04d}"
        r.add(id=fid, desc=f"function number {i}", run=lambda a, i=i: {"fn": i, "args": a})
    return r


class FakeClient:
    """Returns scripted replies in order; records the prompts it saw."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.prompts = []

    def choose(self, menu_prompt: str) -> str:
        self.prompts.append(menu_prompt)
        if not self._replies:
            raise AssertionError("FakeClient ran out of scripted replies")
        return self._replies.pop(0)


# ---- registry ----

def test_registry_rejects_duplicate_id():
    r = make_registry(1)
    with pytest.raises(RegistryError):
        r.add(id="0001", desc="dup", run=lambda a: None)


def test_registry_rejects_reserved_id():
    r = Registry()
    with pytest.raises(RegistryError):
        r.add(id="NEXT", desc="x", run=lambda a: None)


def test_registry_rejects_multiline_desc():
    r = Registry()
    with pytest.raises(RegistryError):
        r.add(id="0001", desc="line1\nline2", run=lambda a: None)


def test_registry_preserves_order():
    r = make_registry(3)
    assert [f.id for f in r.all()] == ["0001", "0002", "0003"]


# ---- pagination ----

def test_paginate_splits_and_flags_next():
    r = make_registry(5)
    p0 = paginate(r, 0, page_size=3)
    assert [f.id for f in p0.functions] == ["0001", "0002", "0003"]
    assert p0.has_next is True
    assert p0.total_pages == 2
    p1 = paginate(r, 1, page_size=3)
    assert [f.id for f in p1.functions] == ["0004", "0005"]
    assert p1.has_next is False


def test_paginate_clamps_out_of_range():
    r = make_registry(2)
    p = paginate(r, 99, page_size=3)
    assert p.index == 0
    assert [f.id for f in p.functions] == ["0001", "0002"]


# ---- reply parsing ----

def test_parse_clean_id():
    r = make_registry(3)
    p = paginate(r, 0, page_size=3)
    d = parse_reply("0002", p)
    assert d.kind == "pick" and d.function.id == "0002"


def test_parse_id_with_noise():
    r = make_registry(3)
    p = paginate(r, 0, page_size=3)
    d = parse_reply("The answer is 0003.", p)
    assert d.kind == "pick" and d.function.id == "0003"


def test_parse_next_only_when_offered():
    r = make_registry(5)
    p0 = paginate(r, 0, page_size=3)
    assert parse_reply("NEXT", p0).kind == "next"
    p1 = paginate(r, 1, page_size=3)  # last page, no NEXT
    assert parse_reply("NEXT", p1).kind == "unparseable"


def test_parse_id_not_on_page_is_unparseable():
    r = make_registry(5)
    p0 = paginate(r, 0, page_size=3)  # shows 0001-0003
    assert parse_reply("0005", p0).kind == "unparseable"


def test_parse_ambiguous_is_unparseable():
    r = make_registry(3)
    p = paginate(r, 0, page_size=3)
    assert parse_reply("0001 or maybe 0002", p).kind == "unparseable"


def test_render_menu_lists_ids_and_next():
    r = make_registry(5)
    p = paginate(r, 0, page_size=3)
    menu = render_menu("what time is it", p)
    assert "0001" in menu and "0003" in menu and NEXT_TOKEN in menu
    assert "0004" not in menu  # next page not shown


# ---- dispatch loop ----

def test_dispatch_picks_on_first_page():
    r = make_registry(3)
    client = FakeClient(["0002"])
    res = Dispatcher(r, client, page_size=3).dispatch("do thing two")
    assert res.status == "ok" and res.function_id == "0002"
    assert res.result == {"fn": 2, "args": {"request": "do thing two"}}


def test_dispatch_pages_then_picks():
    r = make_registry(5)
    client = FakeClient(["NEXT", "0005"])
    res = Dispatcher(r, client, page_size=3).dispatch("do thing five")
    assert res.status == "ok" and res.function_id == "0005"
    assert len(client.prompts) == 2


def test_dispatch_retries_unparseable_then_succeeds():
    r = make_registry(3)
    client = FakeClient(["???", "0001"])
    res = Dispatcher(r, client, page_size=3, max_retries=1).dispatch("thing one")
    assert res.status == "ok" and res.function_id == "0001"


def test_dispatch_exhausts_on_persistent_garbage():
    r = make_registry(3)
    client = FakeClient(["???", "???", "???", "???", "???"])
    res = Dispatcher(r, client, page_size=3, max_retries=1).dispatch("nonsense")
    assert res.status == "exhausted"


def test_dispatch_reports_function_error():
    r = Registry()
    def boom(args):
        raise RuntimeError("kaboom")
    r.add(id="0001", desc="explodes", run=boom)
    client = FakeClient(["0001"])
    res = Dispatcher(r, client, page_size=3).dispatch("blow up")
    assert res.status == "function-error" and "kaboom" in res.error


def test_dispatch_handles_model_error():
    class DeadClient:
        def choose(self, prompt):
            from edgecall.model import ModelError
            raise ModelError("connection refused")
    r = make_registry(2)
    res = Dispatcher(r, DeadClient(), page_size=3).dispatch("anything")
    assert res.status == "model-error" and "refused" in res.error
