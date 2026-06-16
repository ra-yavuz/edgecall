"""edgecall: route a plain-language request to a pre-registered function,
using a deliberately weak local model and a paginated menu.

Public surface most users need:

    from edgecall.registry import register   # decorate a function file
"""

from .registry import REGISTRY, Function, register  # noqa: F401

__version__ = "0.1.0"
