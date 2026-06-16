"""The decision loop: request in, function result out.

Given a natural-language request, the dispatcher shows the weak model the
first menu page, reads its pick, and either:

  - runs the chosen function and returns its result, or
  - advances to the next page if the model said NEXT, or
  - re-asks the same page if the reply was unparseable (bounded retries).

It walks at most ``max_pages`` pages and re-asks an unparseable page at most
``max_retries`` times, so a confused model can never loop forever. Every
turn is recorded in the returned trace, so a caller can see exactly how the
decision was reached (which is essential when debugging a weak model).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .menu import DEFAULT_PAGE_SIZE, paginate, parse_reply, render_menu
from .model import ModelClient, ModelError
from .registry import Registry


@dataclass
class TraceStep:
    page_index: int
    prompt: str
    raw_reply: str
    decision: str  # "pick:<id>" | "next" | "unparseable" | "model-error"


@dataclass
class DispatchResult:
    status: str  # "ok" | "function-error" | "exhausted" | "model-error"
    function_id: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    trace: List[TraceStep] = field(default_factory=list)


@dataclass
class Dispatcher:
    registry: Registry
    client: ModelClient
    page_size: int = DEFAULT_PAGE_SIZE
    # A page can be re-asked this many extra times when the reply is junk.
    max_retries: int = 1

    def dispatch(self, request: str, args: Optional[Dict[str, Any]] = None) -> DispatchResult:
        args = dict(args or {})
        # The full request is always available to the chosen function under
        # this key, in addition to any explicit args the caller passed.
        args.setdefault("request", request)

        trace: List[TraceStep] = []
        page_index = 0
        total_pages = paginate(self.registry, 0, self.page_size).total_pages

        # Upper bound on model turns: one pass through every page, plus the
        # allowed re-asks per page. Guarantees termination.
        max_turns = total_pages * (1 + self.max_retries) + 1
        retries_on_page = 0

        for _ in range(max_turns):
            page = paginate(self.registry, page_index, self.page_size)
            prompt = render_menu(request, page)
            try:
                raw = self.client.choose(prompt)
            except ModelError as exc:
                trace.append(
                    TraceStep(page.index, prompt, "", "model-error")
                )
                return DispatchResult(
                    status="model-error", error=str(exc), trace=trace
                )

            decision = parse_reply(raw, page)

            if decision.kind == "pick" and decision.function is not None:
                trace.append(
                    TraceStep(page.index, prompt, raw, f"pick:{decision.function.id}")
                )
                return self._run(decision.function.id, args, trace)

            if decision.kind == "next":
                trace.append(TraceStep(page.index, prompt, raw, "next"))
                retries_on_page = 0
                page_index += 1
                continue

            # unparseable
            trace.append(TraceStep(page.index, prompt, raw, "unparseable"))
            if retries_on_page < self.max_retries:
                retries_on_page += 1
                continue  # re-ask the same page
            # Out of retries on this page: move on rather than give up, in
            # case the right function is later in the registry.
            retries_on_page = 0
            if page.has_next:
                page_index += 1
                continue
            break

        return DispatchResult(
            status="exhausted",
            error="model did not pick a function within the page/retry budget",
            trace=trace,
        )

    def _run(self, fid: str, args: Dict[str, Any], trace: List[TraceStep]) -> DispatchResult:
        fn = self.registry.get(fid)
        if fn is None:  # should not happen: the id came from the registry
            return DispatchResult(
                status="exhausted",
                error=f"chosen function {fid!r} vanished from registry",
                trace=trace,
            )
        try:
            result = fn.run(args)
        except Exception as exc:  # noqa: BLE001 - a function's failure is data, not a crash
            return DispatchResult(
                status="function-error",
                function_id=fid,
                error=f"{type(exc).__name__}: {exc}",
                trace=trace,
            )
        return DispatchResult(status="ok", function_id=fid, result=result, trace=trace)
