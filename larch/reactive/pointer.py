"""
Provides a pointer to an attribute
"""
import sys
import operator
from weakref import ref
# __pragma__ ('skip')
from .core import rcontext, pointer_attrgetter, pointer_itemgetter, pointer_resolve
__all__ = ("PointerBase", "Pointer", "PointerMap", "PointerState", "PointerExpression", "SELF",
           "ResolveError", "merge_pointers", "NOTHING")
# __pragma__ ('noskip')
# __pragma__ ('ecom')
"""?
from .pcore import rcontext, pointer_attrgetter, pointer_itemgetter, pointer_resolve
?"""
# __pragma__ ('noecom')


def _check_exception(exc, pointer_state, exception_type, to_transfrom):
    # __pragma__ ('skip')
    type_, _, traceback = sys.exc_info()
    if isinstance(exc, to_transfrom):
        raise exception_type(repr(pointer_state), exc).with_traceback(traceback)

    exc.args += (repr(pointer_state),)
    raise exc.with_traceback(traceback)
    # __pragma__ ('noskip')
    """?
    console.error("Exception in pointer", repr(exc))
    if isinstance(exc, to_transfrom):
        raise exception_type()
    raise exc
    ?"""


def _check_setter_exception(exc, pointer_state, exception_type):
    _check_exception(exc, pointer_state, exception_type,
                     (AttributeError, IndexError, KeyError, ReferenceError))


def _check_getter_exception(exc, pointer_state, exception_type):
    _check_exception(exc, pointer_state, exception_type,
                     (AttributeError, TypeError, IndexError, KeyError, ReferenceError))


class MetaNothing(type):
    def __init__(self, name, bases, dict_):
        super().__init__(name, bases, dict_)

    def __bool__(self):
        return False


class NOTHING(metaclass=MetaNothing):
    pass


_RNOTHING = ref(NOTHING)


# __pragma__ ('opov')
class ResolveError(ValueError):
    def __init__(self, path, original):
        self.path = path
        self.original = original

    def __repr__(self):
        return f"<{self.__class__.__name__} path={self.path} original={repr(self.original)}>"


class StrongRef:
    __slots__ = ("ref",)

    def __init__(self, ref):
        self.ref = ref

    def __call__(self):
        return self.ref


def create_ref(obj):
    try:
        return ref(obj)
    except TypeError:
        return StrongRef(obj)


class PointerState:
    __slots__ = ("root", "path", "accessors")

    def __init__(self, root=_RNOTHING, path=(), accessors=()):
        # root must be a weak reference or a StrongRef
        self.root = root
        self.path = path
        self.accessors = accessors

    def __eq__(self, other):
        if other is not None and self.__class__ == other.__class__:
            return self.root == other.root and self.path == other.path
        return False

    def __ne__(self, other):
        return not (self == other)

    def __bool__(self):
        try:
            self.get()
            return False if self.root is _RNOTHING else True
        except ResolveError:
            return False

    def __len__(self):
        return len(self.accessors)

    def __hash__(self):
        return hash(self.path)

    def new_item(self, index):
        path = self.path + (index,)
        accessors = self.accessors + (pointer_itemgetter(index), )
        return self.create_state(self.root, path, accessors)

    def new_attr(self, name):
        path = self.path + (name,)
        accessors = self.accessors + (pointer_attrgetter(name), )
        return self.create_state(self.root, path, accessors)

    def create_state(self, root, path, accessors):
        return self.__class__(root, path, accessors)

    def get(self):
        return self.delegate_get(self.root())

    def delegate_get(self, root):
        try:
            return pointer_resolve(root, self.accessors)
        except Exception as e:
            _check_getter_exception(e, self, ResolveError)

    def set(self, value, root=None):
        parent, getter, setter = self.split(root)
        try:
            setter(parent, value)
        except Exception as e:
            _check_setter_exception(e, self, ResolveError)
        return value

    def split(self, root=None):
        def setitem(obj, value):
            obj[self.path[-1]] = value

        def setattr_(obj, value):
            setattr(obj, self.path[-1], value)
            return value

        if root is None:
            root = self.root()

        # __pragma__ ('tconv')
        if not self.accessors:
            def invalid_setter(obj, value):
                raise TypeError("cannot set")

            return root, (lambda i: i), invalid_setter
        # __pragma__ ('notconv')

        setter = setitem if type(self.accessors[-1]) is pointer_itemgetter else setattr_
        try:
            parent = pointer_resolve(root, self.accessors[:-1])
        except Exception as e:
            _check_getter_exception(e, self, ResolveError)

        return parent, self.accessors[-1], setter

    def is_same(self, other):
        """returns True if other and self refers to the same object"""
        me = self
        try:
            if len(me.path) < len(other.path):
                other = other.sub_state(len(other.path) - len(me.path))
            else:
                me = me.sub_state(len(me.path) - len(other.path))
        except ResolveError:  # pragma: no cover
            return False

        def tmt(a):
            return tuple(map(type, a))

        if isinstance(me.root, ref):
            if not isinstance(other.root, ref) or me.root() != other.root():
                return False
        elif me.root != other.root:
            return False

        return (me.path == other.path
                and tmt(me.accessors) == tmt(other.accessors))

    def sub_state(self, count):
        """returns a state resolved to count path elements"""
        if not count:
            return self

        access = self.accessors
        try:
            obj = pointer_resolve(self.root(), access[:count])
            return self.create_state(
                ref(obj), self.path[count:], access[count:])
        except Exception as e:  # pragma: no cover
            _check_getter_exception(e, self, ResolveError)

    def merge_to(self, state):
        return self.create_state(state.root, state.path + self.path,
                                 state.accessors + self.accessors)

    def __getstate__(self):
        return self.root(), self.path, self.accessor_to_pickle()

    def __setstate__(self, state):
        root, self.path, accessors = state
        self.root = _RNOTHING if root is NOTHING else create_ref(root)
        self.pickle_to_accessor(accessors)

    def accessor_to_pickle(self):
        mapper = {pointer_itemgetter: "i", pointer_attrgetter: "a"}
        return "".join(mapper[type(a)] for a in self.accessors)

    def pickle_to_accessor(self, state):
        mapper = {"i": pointer_itemgetter, "a": pointer_attrgetter}
        self.accessors = tuple(mapper[g](a) for g, a in zip(state, self.path))

    def __str__(self):
        try:
            return "".join(
                f"[{name}]" if type(accessor) == pointer_itemgetter else f".{name}"
                for accessor, name in zip(self.accessors, self.path))
        except Exception as e:  # pragma: no cover
            e.args += (self.path, )
            raise e

    def __repr__(self):
        return f"{repr(self.root())}{str(self)}"


class _DumyState:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.value == other.value

    def __repr__(self):
        return str(self.value)

    def get(self):
        return self.value

    def delegate_get(self, root):
        return self.value

    def merge_to(self, state):
        return self.value


def dumy_state(a):
    return a if isinstance(a, PointerState) else _DumyState(a)


class _ExpressionRoot:
    # root for PointerExpression
    __slots__ = ("args", )

    def __init__(self, args):
        self.args = tuple(a.__state__ if isinstance(a, Pointer) else dumy_state(a) for a in args)

    def __eq__(self, other):
        if other is not None and self.__class__ == other.__class__:
            return self.args == other.args
        return False

    def merge_args(self, state):
        return (a.merge_to(state) for a in self.args)

    def merge_to(self, state):
        return self.__class__(self.merge_args(state))

    def __getstate__(self):
        return self.args

    def __setstate__(self, state):
        self.args = state


class _ExpressionOperandRoot(_ExpressionRoot):
    __slots__ = ("operand", "kwargs")

    def __init__(self, operand, args, kwargs):
        super().__init__(args)
        self.operand = operand
        self.kwargs = {
            k: v.__state__ if isinstance(v, Pointer) else _DumyState(v)
            for k, v in kwargs.items()}

    def __eq__(self, other):
        if super().__eq__(other):
            return self.operand == other.operand
        return False

    def __call__(self):
        args = [a.get() for a in self.args]
        kwargs = {k: v.get() for k, v in self.kwargs.items()}
        return self.apply(args, kwargs)

    def evaluate(self, root):
        # like call but with different root in argument
        args = [a.delegate_get(root) for a in self.args]
        kwargs = {k: v.delegate_get(root) for k, v in self.kwargs.items()}
        return self.apply(args, kwargs)

    def apply(self, args, kwargs):
        return self.operand(*args, **kwargs)

    def __repr__(self):
        return f"{self.operand.__name__}{self.args}{self.kwargs}"

    def merge_kwargs(self, state):
        return {k: v.merge_to(state) for k, v in self.kwargs.items()}

    def merge_to(self, state):
        return self.__class__(self.operand, self.merge_args(state),
                              self.merge_kwargs(state))

    def __getstate__(self):
        return self.operand, self.args, self.kwargs

    def __setstate__(self, state):
        try:
            self.operand, self.args, self.kwargs = state
        except ValueError:
            self.operand, self.args = state
            self.kwargs = {}


class _ExpressionOperandRootApply(_ExpressionOperandRoot):
    def apply(self, args, kwargs):
        return self.operand(args)


class _ExpressionAndRoot(_ExpressionRoot):
    def __call__(self):
        return self.apply(lambda v: v.get())

    def evaluate(self, root):
        return self.apply(lambda v: v.delegate_get(root))

    def apply(self, getter):
        try:
            values = (getter(a) for a in self.args)
            v = False
            # __pragma__ ('tconv')
            for v in values:
                if not v:
                    return False
            # __pragma__ ('notconv')
            return v
        except Exception:
            return False

    def __repr__(self):
        return f"and{self.args}"


class _ExpressionOrRoot(_ExpressionRoot):
    def __call__(self):
        return self.apply(lambda v: v.get())

    def evaluate(self, root):
        return self.apply(lambda v: v.delegate_get(root))

    def apply(self, getter):
        def eval_(v):
            try:
                v = getter(v)
            except Exception:
                return False
            return v

        values = (eval_(a) for a in self.args)
        # __pragma__ ('tconv')
        for v in values:
            if v:
                return v
        # __pragma__ ('notconv')
        return v

    def __repr__(self):
        return f"or{self.args}"


class PointerExpression(PointerState):
    """A pointer expression"""

    def set(self, value, root=None):
        raise ValueError("Cannot set PointerExpression", self)

    def get(self):
        return super().delegate_get(self.root())

    def delegate_get(self, root):
        return super().delegate_get(self.root.evaluate(root))

    def merge_to(self, state):
        root = self.root.merge_to(state)
        return self.create_state(root, self.path, self.accessors)

    # __pragma__ ('kwargs')
    @classmethod
    def make(cls, pointer, operand, *args, **kwargs):
        return pointer.__class__(cls(_ExpressionOperandRoot(operand, args, kwargs)))
    # __pragma__ ('nokwargs')

    @classmethod
    def make_and(cls, pointer, *args):
        return pointer.__class__(cls(_ExpressionAndRoot(args)))

    @classmethod
    def make_or(cls, pointer, *args):
        return pointer.__class__(cls(_ExpressionOrRoot(args)))

    # __pragma__ ('kwargs')
    @classmethod
    def call(cls, func, *args, **kwargs):
        """calls func with args"""
        return Pointer(cls(_ExpressionOperandRoot(func, args, kwargs)))
    # __pragma__ ('nokwargs')

    @classmethod
    def apply(cls, func, *args):
        return Pointer(cls(_ExpressionOperandRootApply(func, args, {})))

    def __getstate__(self):
        return self.root, self.path, self.accessor_to_pickle()

    def __setstate__(self, state):
        self.root, self.path, accessors = state
        self.pickle_to_accessor(accessors)

    def __repr__(self):
        return f"{repr(self.root)}{self}"


class PointerBase:
    __slots__ = ()


class Pointer(PointerBase):
    """
    A placeholder to an object attributes and index chain (a generalization to
    attrgetter/itemgetter of module operator) to construct a pointer you call

    >>> pointer = Pointer(obj).a[0]

    to get a pointer's value you call

    >>> value = pointer()  # same as obj.a[0]

    to set a pointer's value you call

    >>> pointer(value)  # same as obj.a[0] = value
    """
    __slots__ = ("__state__", "__weakref__")

    def __init__(self, state_or_obj=None):
        if state_or_obj is None:
            state_or_obj = PointerState()

        elif isinstance(state_or_obj, Pointer):
            state_or_obj = state_or_obj.__state__

        elif not isinstance(state_or_obj, PointerState):
            state_or_obj = PointerState(create_ref(state_or_obj))

        self.__state__ = state_or_obj

    def __get__(self, holder, owner):
        # delegator handler
        if holder is None:
            return self

        return self.__state__.delegate_get(holder)

    def __set__(self, holder, value):
        # delegator handler
        self.__state__.set(value, holder)

    def __bool__(self):
        return bool(self.__state__)

    def __getitem__(self, index):
        return self.__class__(self.__state__.new_item(index))

    def __getattr__(self, name):
        return self.__class__(self.__state__.new_attr(name))

    def __call__(self, value=NOTHING):
        return self.__state__.get() if value is NOTHING else self.__state__.set(value)

    def __hash__(self):
        return hash(self.__state__)

    def __eq__(self, other):
        if other is not None and self.__class__ == other.__class__:
            return self.__state__.is_same(other.__state__)

        return False

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        with rcontext.untouched:
            return str(self.__state__)

    def __len__(self):
        return 0

    def __iter__(self):
        raise TypeError("cannot iter %r" % self)

    def __repr__(self):
        return f"<{self.__class__.__name__}-{repr(self.__state__)}>"

    def __add__(self, other):
        return PointerExpression.make(self, operator.add, self, other)

    def __radd__(self, other):
        return PointerExpression.make(self, operator.add, other, self)

    def __sub__(self, other):
        return PointerExpression.make(self, operator.sub, self, other)

    def __rsub__(self, other):
        return PointerExpression.make(self, operator.sub, other, self)

    def __truediv__(self, other):
        return PointerExpression.make(self, operator.truediv, self, other)

    def __rtruediv__(self, other):
        return PointerExpression.make(self, operator.truediv, other, self)

    def __mul__(self, other):
        return PointerExpression.make(self, operator.mul, self, other)

    def __rmul__(self, other):
        return PointerExpression.make(self, operator.mul, other, self)

    def __and__(self, other):
        return PointerExpression.make_and(self, self, other)

    def __rand__(self, other):
        return PointerExpression.make_and(self, other, self)

    def __or__(self, other):
        return PointerExpression.make_or(self, self, other)

    def __ror__(self, other):
        return PointerExpression.make_or(self, other, self)

    def __reduce_ex__(self, protocol):
        return self.__class__, (self.__state__,)


SELF = Pointer()
"""This is actually not a Pointer but a trivial delegator"""


class PointerMap:
    """A named value container which is able to handle pointer values"""
    __slots__ = ("__values", )

    # __pragma__ ('kwargs')
    def __init__(self, **kwargs):
        self.__values = kwargs
    # __pragma__ ('nokwargs')

    def get(self, key, default=NOTHING):
        value = self.__values.get(key, default)
        if isinstance(value, PointerBase):
            return value()

        elif value is NOTHING:
            raise KeyError(key)

        return value

    def set(self, key, value):
        """Returns True if the key was a pointer"""
        val = self.__values.get(key, None)
        if isinstance(val, PointerBase) and not isinstance(value, PointerBase):
            val(value)
            return True

        self.__values[key] = value
        return False

    def remove(self, key):
        self.__values.pop(key, None)

    def update(self, dictionary):
        self.__values.update(dictionary)

    def keys(self):
        return self.__values.keys()

    def raw(self, key):
        return self.__values.get(key)

    def __contains__(self, key):
        return key in self.__values


def merge_pointers(*pointers):
    """
    Merges several pointers together.

    Args:
        pointers: multiple pointers to merge

    Returns:
        Pointer: a chained pointer object.

    Example:
        >>> p1 = Pointer(obj1).a.b
        >>> p2 = Pointer(obj2).c.d
        >>> p3 = merge_pointers(p1, p2)
        >>> p3 == Pointer(obj1).a.b.c.d
    """
    states = (p.__state__ for p in pointers)
    state = next(states)
    for s in states:
        state = s.merge_to(state)

    return Pointer(state)
