"""edgecall command-line entrypoint.

  edgecall serve                 run the HTTP API
  edgecall dispatch "<request>"  route one request from the CLI (no server)
  edgecall functions             list registered functions
  edgecall --help                usage (carries the liability disclaimer)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import __version__
from .config import DISCLAIMER, Config


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--functions-dir", help="directory of drop-in function files")
    p.add_argument("--model-base-url", help="OpenAI-compatible endpoint base URL")
    p.add_argument("--model", dest="model_name", help="model name to request")
    p.add_argument("--api-key", dest="model_api_key", help="bearer token (often unused locally)")
    p.add_argument("--page-size", type=int, help="functions shown per menu page")
    p.add_argument("--max-retries", type=int, help="re-asks per page on an unparseable reply")


def _config_from_args(args: argparse.Namespace) -> Config:
    return Config.resolve(
        functions_dir=getattr(args, "functions_dir", None),
        model_base_url=getattr(args, "model_base_url", None),
        model_name=getattr(args, "model_name", None),
        model_api_key=getattr(args, "model_api_key", None),
        host=getattr(args, "host", None),
        port=getattr(args, "port", None),
        page_size=getattr(args, "page_size", None),
        max_retries=getattr(args, "max_retries", None),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edgecall",
        description=(
            "Route a plain-language request to one of your pre-registered "
            "functions, using a deliberately weak local model and a "
            "paginated menu. Talks to any OpenAI-compatible endpoint.\n\n"
            "DISCLAIMER: " + DISCLAIMER
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"edgecall {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="run the HTTP API")
    p_serve.add_argument("--host", help="bind host (default 127.0.0.1)")
    p_serve.add_argument("--port", type=int, help="bind port (default 8900)")
    _add_common(p_serve)

    p_disp = sub.add_parser("dispatch", help="route one request from the CLI")
    p_disp.add_argument("request", help="the natural-language request")
    p_disp.add_argument("--trace", action="store_true", help="print the decision trace")
    _add_common(p_disp)

    p_fns = sub.add_parser("functions", help="list registered functions")
    _add_common(p_fns)

    return parser


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn  # imported lazily so `dispatch`/`functions` work without it

    from .server import build_app

    cfg = _config_from_args(args)
    app = build_app(cfg)
    print(f"edgecall {__version__}: {len(app.state.loaded_files)} function file(s) loaded")
    print(f"serving on http://{cfg.host}:{cfg.port}  (model: {cfg.model_base_url})")
    print("DISCLAIMER: " + DISCLAIMER)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    from .dispatcher import Dispatcher
    from .loader import load_functions_dir
    from .model import ModelClient
    from .registry import REGISTRY

    cfg = _config_from_args(args)
    load_functions_dir(cfg.functions_dir)
    client = ModelClient(base_url=cfg.model_base_url, model=cfg.model_name,
                         api_key=cfg.model_api_key)
    disp = Dispatcher(REGISTRY, client, page_size=cfg.page_size, max_retries=cfg.max_retries)
    res = disp.dispatch(args.request)
    out = {
        "status": res.status,
        "function_id": res.function_id,
        "result": res.result,
        "error": res.error,
    }
    if args.trace:
        out["trace"] = [asdict(s) for s in res.trace]
    print(json.dumps(out, indent=2))
    return 0 if res.status == "ok" else 1


def _cmd_functions(args: argparse.Namespace) -> int:
    from .loader import load_functions_dir
    from .registry import REGISTRY

    cfg = _config_from_args(args)
    load_functions_dir(cfg.functions_dir)
    for fn in REGISTRY.all():
        print(f"{fn.id}  {fn.desc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        return _cmd_serve(args)
    if args.command == "dispatch":
        return _cmd_dispatch(args)
    if args.command == "functions":
        return _cmd_functions(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
