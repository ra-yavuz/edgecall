"""Autoloader for drop-in function files.

edgecall imports every ``*.py`` file in a functions directory at startup.
Importing the file runs its ``@register`` decorators, which populate the
global registry. This is the whole extension model: drop a file in, restart,
done. No central list to edit.

Files are loaded in sorted filename order, which is therefore the
registration order, which is therefore the pagination order. Name files
with a numeric prefix (``0001_gold_price.py``) to control where they land
in the menu; put your most-used functions first.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List

from .registry import REGISTRY, RegistryError


class LoaderError(RuntimeError):
    pass


def load_functions_dir(path: str | Path) -> List[str]:
    """Import every top-level ``*.py`` under ``path`` (sorted by name).

    Returns the list of loaded file names. Raises LoaderError on a bad
    file rather than silently skipping it: a function that fails to load is
    a function the model can never reach, and a silent skip would hide that.
    """
    directory = Path(path)
    if not directory.is_dir():
        raise LoaderError(f"functions directory does not exist: {directory}")

    loaded: List[str] = []
    # Hidden files and dunder files (e.g. __init__.py, __pycache__) are not
    # function modules; skip them deliberately.
    py_files = sorted(
        p
        for p in directory.glob("*.py")
        if not p.name.startswith("_") and not p.name.startswith(".")
    )

    for py in py_files:
        # Give each module a stable, unique name so re-imports and tracebacks
        # are sane, without colliding with real packages.
        mod_name = f"edgecall_function_{py.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, py)
        if spec is None or spec.loader is None:
            raise LoaderError(f"could not create import spec for {py}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except RegistryError as exc:
            # A bad registration (dup id, empty desc) is the author's
            # mistake; surface it with the file name so it is fixable.
            raise LoaderError(f"{py.name}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - we want the file name attached
            raise LoaderError(f"{py.name}: failed to import: {exc}") from exc
        loaded.append(py.name)

    if not REGISTRY.all():
        raise LoaderError(
            f"no functions registered after loading {directory} "
            f"({len(py_files)} .py file(s) seen). "
            "Each function file must call @register."
        )

    return loaded
