from .version import __version__
from .base import (
    rule, SimpleReactive, MetaReactive, Reactive, cells_of, atomic, untouched, touched, silent,
    reactive, call_outside)
from .pointer import (
    PointerBase, Pointer, PointerMap, PointerState, PointerExpression, SELF, ResolveError,
    merge_pointers, NOTHING)
from .cell import Cell, MakeCell, ResetCell, TypeCell, MakeTypeCell
from .agent import Agent, CellAgent, OldAgent, old, cell
# __pragma__ ('skip')
from .core import (
    rcontext, CellBase, ReactiveState, Subject, Container, ResetContainer, Rule, IterRule,
    pointer_attrgetter, pointer_itemgetter, pointer_resolve, ReactiveWarning, core)

__all__ = (
    "__version__",
    "rcontext", "CellBase", "ReactiveState", "Subject", "Container", "ResetContainer", "Rule",
    "IterRule", "pointer_attrgetter", "pointer_itemgetter", "pointer_resolve", "ReactiveWarning",
    "core",

    "rule", "SimpleReactive", "MetaReactive", "Reactive", "cells_of", "atomic", "untouched",
    "touched", "silent", "reactive", "call_outside",

    "PointerBase", "Pointer", "PointerMap", "PointerState", "PointerExpression", "SELF",
    "ResolveError", "merge_pointers", "NOTHING",

    "Cell", "MakeCell", "ResetCell", "TypeCell", "MakeTypeCell",

    "Agent", "CellAgent", "OldAgent", "old", "cell")

# backward compatibility
ProxyBase = PointerBase
Proxy = Pointer
ProxyMap = PointerMap
ProxyState = PointerState
ProxyExpression = PointerExpression


def add_pickle_extensions():
    import copyreg
    from hashlib import md5

    def add_extension_by_hash(module, name):
        # prepare for the future
        code = int(md5((module + ":" + name).encode("ascii")).hexdigest(), 16)
        copyreg._inverted_registry[code] = (module, name)

        # backward compatible to old proxy module
        module_name = module.replace(".pointer", ".proxy") + ":" + name.replace("Pointer", "Proxy")
        code = int(md5((module_name).encode("ascii")).hexdigest(), 16)
        copyreg.add_extension(module, name, code & 0x7FFFFFFF)

    add_extension_by_hash("larch.reactive.pointer", "_ExpressionOperandRootApply")
    add_extension_by_hash("larch.reactive.pointer", "_ExpressionOperandRoot")
    add_extension_by_hash("larch.reactive.pointer", "_ExpressionAndRoot")
    add_extension_by_hash("larch.reactive.pointer", "_ExpressionOrRoot")
    add_extension_by_hash("larch.reactive.pointer", "_DumyState")
    add_extension_by_hash("larch.reactive.pointer", "PointerExpression")
    add_extension_by_hash("larch.reactive.pointer", "PointerState")
    add_extension_by_hash("larch.reactive.pointer", "Pointer")
    add_extension_by_hash("larch.reactive.pointer", "NOTHING")
# __pragma__ ('noskip')


# __pragma__ ('ecom')
"""?
from .pcore import (
    rcontext, CellBase, ReactiveState, Subject, Container, ResetContainer, Rule, IterRule,
    pointer_attrgetter, pointer_itemgetter, pointer_resolve, ReactiveWarning, core)
?"""
# __pragma__ ('noecom')
