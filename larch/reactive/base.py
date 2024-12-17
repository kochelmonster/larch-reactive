import sys
import warnings
from operator import itemgetter, attrgetter
from weakref import ref
# __pragma__ ('skip')
from functools import wraps
from inspect import isgeneratorfunction
from .core import rcontext, IterRule, Rule, CellBase, ReactiveState
__all__ = ("rule", "SimpleReactive", "MetaReactive", "Reactive", "cells_of",
           "atomic", "untouched", "touched", "silent", "reactive", "call_outside")
# __pragma__ ('noskip')
# __pragma__ ('ecom')
"""?
from .pcore import rcontext, IterRule, CellBase, ReactiveState
?"""


def atomic():
    """Returns an atomic decorator context"""
    return rcontext.atomic


def untouched():
    """Returns an untouched decorator context"""
    return rcontext.untouched


def touched():
    """Returns a touched decorator context"""
    return rcontext.touched


def silent():
    """Returns a slient decorator context"""
    return rcontext.silent


_rule_call_ = 0


def rule(level=0):
    """
    A decorator converting a method to a rule.

    Args:
        level (int): A "hard" priority level. Rules with smaller levels will
            allways be called before rules of greater levels.
    """

    global _rule_call_

    internal_rule_order = _rule_call_
    _rule_call_ += 1

    def irule(method, lvl=level, internal_order=internal_rule_order):
        # __pragma__ ('skip')
        @wraps(method)
        def call_rule(self, *args, **kwargs):
            if rcontext.inside_rule:
                return method(self, *args, **kwargs)

            # this is not done very often so we take the long
            # way to find the rule
            methods = (r for r in self.__reactive_rules__ if r.method is method)
            with atomic():
                try:
                    next(methods).notify(args, kwargs)
                except StopIteration:  # pragma: no cover
                    return method(self, *args, **kwargs)

        rule = IterRule if isgeneratorfunction(method) else Rule
        call_rule.__rule__ = (rule, lvl, internal_order, method)
        return call_rule
        # __pragma__ ('noskip')
        """?
        if not method.__rule__:
            method.__rule__ = (IterRule, lvl, internal_order, method)
        return method
        ?"""

    if not isinstance(level, int):
        return irule(level, 0)

    return irule


class SimpleReactive:
    """
    The base class for reactive objects that can hold cells and/or rules.
    Can also be used in multiple inheritance trees.
    """

    __reactive_state__ = None
    """An instance attribute holding the reference to a ReactiveState object"""

    __reactive_rules__ = None
    """
    An instance attribute, holding a tuple with all rule objects
    belonging to a reactive instance. This container is used, to prevent
    the rules objects from beeing deleted.
    """

    __reactive_rule_methods__ = None
    """A class attribute holding a tuple of all methods defined as rules"""

    __reactive_cells__ = None
    """A class attribute holding a dictionary of all cells with name"""

    @classmethod
    def __make_reactive__(cls):
        """converts an ordinary python class to a reactive python class"""
        cls.__replace_init__()
        cls.__init_reactive_attributes__()

    @classmethod
    def __init_reactive_attributes__(cls):
        cells, rules = cls.__collect_reactive_attributes__()
        cls.__reactive_rule_methods__ = tuple(rules)

        # Each class must have its own Cell Instances
        # to ensure an unqiue cell index
        d = dict(cls.__dict__)  # dict conversion for pyjs
        for i, (n, c) in enumerate(cells.items()):
            if n not in d:
                c = cells[n] = c.copy()

            c.__init_cell__(n, i)
            setattr(cls, n, c)

        cls.__reactive_cells__ = cells

    @classmethod
    def __collect_reactive_attributes__(cls):
        """collect all cells and rules of a class"""
        rules = []
        cells = {}

        for n in dir(cls):
            obj = getattr(cls, n)
            if isinstance(obj, CellBase):
                cells[n] = obj
            else:
                rule_props = getattr(obj, "__rule__", None)
                if isinstance(rule_props, tuple):
                    # factory, level, internal_order, method = rule_props
                    rules.append(rule_props)

        rules.sort(key=itemgetter(1, 2))
        return cells, rules

    @classmethod
    def __replace_init__(cls):
        """
        wraps the original __init__ function with a reactive __init__
        function that, initializes all rules and cells.
        """

        # __pragma__ ('kwargs')
        def _rinit_(self, *args, **kwargs):
            if self.__reactive_state__ is None:
                self.__reactive_state__ = ReactiveState(self)
                cls.__org_init__(self, *args, **kwargs)
                self.__init_rules__(self.__reactive_rule_methods__)
            else:
                cls.__org_init__(self, *args, **kwargs)
        # __pragma__ ('nokwargs')

        cls.__org_init__ = cls.__init__
        cls.__init__ = _rinit_  # __: skip
        # __pragma__('js', '{}', 'Object.defineProperty(cls, "__init__", {value: _rinit_});')

    def __init_rules__(self, rules):
        """Initializes all rules of a reactive object"""
        wself = ref(self)
        crules = [factory(wself, method, level, internal_order)
                  for factory, level, internal_order, method in rules]
        # __pragma__ ('tconv')
        if crules:
            self.__reactive_rules__ = crules
            with atomic():
                rcontext.emit(crules)
        # __pragma__ ('notconv')

    # __pragma__ ('kwargs')
    def __init__(self, *args, **kwargs):
        if kwargs:
            cell_names = self.__reactive_cells__.keys()
            cell_names = frozenset(cell_names).intersection(kwargs.keys())
            for n in cell_names:
                setattr(self, n, kwargs.pop(n))
        super().__init__(*args, **kwargs)
    # __pragma__ ('nokwargs')

    # __pragma__ ('skip')
    def __getstate__(self):
        state = {}
        state.update(self.__dict__)
        state.pop("__reactive_rules__", None)
        state["__reactive_state__"] = state["__reactive_state__"].as_dict(self)
        return state

    def __setstate__(self, state):
        cstate = {}  # copy state the original should not be changed
        cstate.update(state)

        rstate = cstate.pop("__reactive_state__")
        self.__dict__.update(cstate)

        self.__reactive_state__ = ReactiveState(self)
        self.__reactive_state__.from_dict(self, rstate)
        self.__init_rules__(self.__reactive_rule_methods__)

        # update the state a second time
        # because __init_rules__ could have change it accidently
        self.__reactive_state__.from_dict(self, rstate)
        self.__dict__.update(cstate)
    # __pragma__ ('noskip')


class MetaReactive(type):
    def __init__(self, name, bases, dict_):
        super().__init__(name, bases, dict_)
        self.__make_reactive__()


class Reactive(SimpleReactive, metaclass=MetaReactive):
    pass


def cells_of(reactive):
    """
    Returns all cell containers of an reactive object.

    Args:
        reactive: A reactive object.

    Returns:
        list: All reactive cell containers of `reactive`.
    """
    return sorted(reactive.__reactive_cells__.values(), key=attrgetter("order"))


# __pragma__ ('skip')
def reactive(cls):
    """A class decorator making a class reactive."""
    if not issubclass(cls, SimpleReactive):
        bases = (SimpleReactive, ) + cls.__bases__
        attribs = dict(cls.__dict__)
        cls = type(cls.__name__, bases, attribs)
    cls.__make_reactive__()
    return cls
# __pragma__ ('noskip')


def call_outside(func, *args, **kwargs):
    """
    Postpones the execution of `func` until the current atomic operation has
    finished. If called outside an atomic operation `func` is executed
    immediate.

    Args:
        func (callable): The callable to execute.
        *args: Arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        callable: the given `func`
    """
    def caller(f=func, args=(args, kwargs)):
        try:
            f(*args[0], **args[1])
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
            # __pragma__ ('skip')
            from .exception import format_full_exception_tb
            tb = format_full_exception_tb()
            # __pragma__ ('noskip')
            tpl = 'Exception while executing outside call:  {}({}) "{}"\n{}'
            warnings.warn(tpl.format(f, args, exc_value, tb))
    caller.__name__ = func.__name__
    rcontext.push_callback(caller)
    return func
# __pragma__ ('noecom')
