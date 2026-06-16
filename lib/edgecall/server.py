"""HTTP server for edgecall.

Two surfaces over the same dispatcher:

  POST /v1/dispatch
      edgecall-native. Body: {"request": "...", "args": {...}, "trace": false}
      Returns the structured DispatchResult. This is the honest interface:
      you get the chosen function id, its result, and optionally the full
      decision trace.

  POST /v1/chat/completions
      OpenAI-compatible shim so existing OpenAI clients can drive edgecall
      without changes. The last user message is taken as the request; the
      function result is returned as the assistant message content (JSON
      encoded). This is a convenience wrapper, not a real chat model: there
      is no conversation, no token streaming, one request -> one function.

  GET /healthz, GET /v1/functions, GET /  (info + disclaimer)
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import DISCLAIMER, Config
from .dispatcher import Dispatcher
from .loader import load_functions_dir
from .menu import paginate
from .model import ModelClient
from .registry import REGISTRY


class DispatchRequest(BaseModel):
    request: str = Field(..., description="natural-language request to route")
    args: Dict[str, Any] = Field(default_factory=dict)
    trace: bool = Field(default=False, description="include the decision trace")


def build_app(config: Config) -> FastAPI:
    """Load functions, wire the dispatcher, and return the FastAPI app."""
    loaded = load_functions_dir(config.functions_dir)

    client = ModelClient(base_url=config.model_base_url, model=config.model_name,
                         api_key=config.model_api_key)
    dispatcher = Dispatcher(
        registry=REGISTRY,
        client=client,
        page_size=config.page_size,
        max_retries=config.max_retries,
    )

    app = FastAPI(title="edgecall", version=__version__)
    # Stash for handlers / tests.
    app.state.config = config
    app.state.dispatcher = dispatcher
    app.state.loaded_files = loaded

    def _result_payload(req: DispatchRequest) -> Dict[str, Any]:
        res = dispatcher.dispatch(req.request, req.args)
        payload: Dict[str, Any] = {
            "status": res.status,
            "function_id": res.function_id,
            "result": res.result,
            "error": res.error,
        }
        if req.trace:
            payload["trace"] = [asdict(step) for step in res.trace]
        return payload

    @app.get("/", response_class=PlainTextResponse)
    def root() -> str:
        funcs = REGISTRY.all()
        pages = paginate(REGISTRY, 0, config.page_size).total_pages
        lines = [
            f"edgecall {__version__}",
            "",
            "Route a plain-language request to one of your registered",
            "functions using a weak local model and a paginated menu.",
            "",
            f"functions loaded : {len(funcs)} (across {pages} menu page(s))",
            f"model endpoint   : {config.model_base_url} ({config.model_name})",
            "",
            "POST /v1/dispatch            edgecall-native dispatch",
            "POST /v1/chat/completions    OpenAI-compatible shim",
            "GET  /v1/functions           list registered functions",
            "GET  /healthz                liveness",
            "",
            "DISCLAIMER: " + DISCLAIMER,
        ]
        return "\n".join(lines)

    @app.get("/healthz")
    def healthz() -> Dict[str, Any]:
        return {"ok": True, "functions": len(REGISTRY)}

    @app.get("/v1/functions")
    def list_functions() -> Dict[str, Any]:
        return {
            "functions": [
                {"id": fn.id, "description": fn.desc} for fn in REGISTRY.all()
            ]
        }

    @app.post("/v1/dispatch")
    def dispatch(req: DispatchRequest) -> Dict[str, Any]:
        return _result_payload(req)

    @app.post("/v1/chat/completions")
    def chat_completions(body: Dict[str, Any]) -> JSONResponse:
        # Take the last user message as the request. This is the minimal
        # mapping that lets an OpenAI client talk to edgecall unmodified.
        messages = body.get("messages") or []
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "no user message in request"}},
            )
        request_text = str(user_msgs[-1].get("content", "")).strip()
        res = dispatcher.dispatch(request_text)

        content = json.dumps(
            {
                "status": res.status,
                "function_id": res.function_id,
                "result": res.result,
                "error": res.error,
            }
        )
        # A minimal OpenAI ChatCompletion object. id/created are fixed-ish:
        # edgecall is not a chat model, so we do not fabricate token counts.
        return JSONResponse(
            content={
                "id": "edgecall-dispatch",
                "object": "chat.completion",
                "model": body.get("model", config.model_name),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            }
        )

    return app
