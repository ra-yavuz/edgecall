"""Runtime configuration, resolved from CLI flags and environment.

Everything is overridable so the same package runs identically from a clone
(point at ./functions) and from an installed .deb (point at the system
functions dir). Precedence: explicit CLI flag > environment variable >
built-in default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DISCLAIMER = (
    "edgecall is provided AS IS, WITHOUT WARRANTY OF ANY KIND. It runs "
    "functions you register, on inputs chosen by an unreliable language "
    "model, and exposes an HTTP API on a local port. The author is not "
    "liable for any damage to hardware, data, or system, or for the content "
    "of model output or function results. You accept all risk."
)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


@dataclass
class Config:
    # Where drop-in function files live.
    functions_dir: str
    # OpenAI-compatible endpoint to ask which function to run.
    model_base_url: str
    model_name: str
    model_api_key: Optional[str]
    # Server bind.
    host: str
    port: int
    # Pagination + loop budget.
    page_size: int
    max_retries: int

    @classmethod
    def resolve(
        cls,
        *,
        functions_dir: Optional[str] = None,
        model_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        model_api_key: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        page_size: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> "Config":
        fdir = (
            functions_dir
            or _env("EDGECALL_FUNCTIONS_DIR")
            or _default_functions_dir()
        )
        return cls(
            functions_dir=str(fdir),
            model_base_url=(
                model_base_url
                or _env("EDGECALL_MODEL_BASE_URL", "http://localhost:11434/v1")
            ),
            model_name=model_name or _env("EDGECALL_MODEL", "phi3"),
            model_api_key=model_api_key or _env("EDGECALL_API_KEY"),
            host=host or _env("EDGECALL_HOST", "127.0.0.1"),
            port=int(port or _env("EDGECALL_PORT", "8900")),
            page_size=int(page_size or _env("EDGECALL_PAGE_SIZE", "3")),
            max_retries=int(max_retries or _env("EDGECALL_MAX_RETRIES", "1")),
        )


def _default_functions_dir() -> str:
    """Prefer a functions/ next to the installed package, else the system
    location used by the .deb, else a relative ./functions for a clone."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent.parent / "functions",  # repo clone: <repo>/functions
        Path("/usr/share/edgecall/functions"),  # .deb install location
        Path.cwd() / "functions",
    ]
    for c in candidates:
        if c.is_dir():
            return str(c)
    # Fall back to the first candidate's path; the loader will raise a clear
    # error if it does not exist, which is better than guessing silently.
    return str(candidates[0])
