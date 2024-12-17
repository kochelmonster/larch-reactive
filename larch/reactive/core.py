import os
import platform
try:
    if platform.python_implementation() != "CPython":
        raise ImportError()

    if os.environ.get("LARCH_REACTIVE", "cython") != "cython":
        raise ImportError()

    from .ccore import (
        rcontext, CellBase, ReactiveState, Subject, Container, ResetContainer, Rule, IterRule,
        pointer_attrgetter, pointer_itemgetter, pointer_resolve, ReactiveWarning)
    core = "c"
except ImportError:
    from .pcore import (
        rcontext, CellBase, ReactiveState, Subject, Container, ResetContainer, Rule, IterRule,
        pointer_attrgetter, pointer_itemgetter, pointer_resolve, ReactiveWarning)
    core = "python"

__all__ = (
    "rcontext", "CellBase", "ReactiveState", "Subject", "Container", "ResetContainer", "Rule",
    "IterRule", "pointer_attrgetter", "pointer_itemgetter", "pointer_resolve", "ReactiveWarning",
    "core")
