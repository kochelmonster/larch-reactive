# depreceated module
from .pointer import (
    PointerBase, Pointer, PointerMap, PointerState, PointerExpression, SELF,
    ResolveError, merge_pointers, NOTHING, _DumyState, _ExpressionRoot, _ExpressionOperandRoot,
    _ExpressionOperandRootApply, _ExpressionAndRoot, _ExpressionOrRoot)

__all__ = ("NOTHING", "SELF", "ResolveError", "_DumyState", "_ExpressionRoot", "_ExpressionOrRoot",
           "_ExpressionOperandRoot", "_ExpressionOperandRootApply", "_ExpressionAndRoot")

ProxyBase = PointerBase
Proxy = Pointer
ProxyMap = PointerMap
ProxyState = PointerState
ProxyExpression = PointerExpression
merge_proxies = merge_pointers
