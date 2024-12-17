"""reactive agent"""
from .pointer import Pointer, ResolveError, _check_getter_exception
# __pragma__ ('skip')
from .core import rcontext, Container, CellBase
__all__ = ("Agent", "CellAgent", "OldAgent", "old", "cell")
# __pragma__ ('noskip')
# __pragma__ ('ecom')
"""?
from .pcore import rcontext, Container, CellBase
?"""
# __pragma__ ('noecom')


class Agent:
    def __init__(self, src):
        self.__src__ = src

    def __dir__(self):
        return self.__src__.__reactive_cells__.keys()

    def __getattr__(self, name):
        src = self.__src__
        cell = getattr(src.__class__, name)

        if isinstance(cell, Pointer):
            src, getter, setter = cell.__state__.split(src)
            try:
                cell = getter(src.__class__)
            except Exception:
                _check_getter_exception(cell.__state__, ResolveError)

            if not isinstance(cell, CellBase):
                raise TypeError("Attribute does not point to a cell", name)

        return cell.get_container(src)


class CellAgent(Agent):
    """returns cell containers as attributes"""

    def __setattr__(self, name, value):
        if name == "__src__":
            super().__setattr__(name, value)
        else:
            if isinstance(value, Container):
                cell = getattr(self.__src__.__class__, name)
                cell.set_container(self.__src__, value)
            else:
                raise TypeError("%r must be of type container" % value)


class OldAgent(Agent):
    """returns old cell values as attributes"""

    def __getattr__(self, name):
        try:
            container = super().__getattr__(name)
        except AttributeError:
            return getattr(self.__src__, name)

        # the default container.get_value() also touches the container
        return rcontext.old_values.get(id(container), container.get_value())


def _get_holder_cell(obj):
    holder, getter, setter = obj.__state__.split()
    try:
        return holder, getter(holder.__class__)
    except Exception as e:
        _check_getter_exception(e, obj.__state__, ResolveError)


def old(obj):
    """
    Returns an `old`-agent of `obj`. This function is helpfull within a rule,
    to access the old cell values before the current atomic operation.

    Args:
        obj (Reactive): A reactive object.

    Returns:
        An agent object offering the same attributes as `obj`, with the
        old cell values.
    """
    if isinstance(obj, Pointer):
        holder, cell = _get_holder_cell(obj)
        try:
            container = cell.get_container(holder)
        except AttributeError:
            return obj()
        return rcontext.old_values.get(id(container), container.get_value())
    else:
        return OldAgent(obj)


def cell(obj, value=None):
    """
    Returns a `cell`-agent of `obj`. This function can be used to manipulate
    the cell containers of `obj`.

    Args:
        obj (Reactive): A reactive object.

    Returns:
        An agent object offering the same attributes as `obj`, with the cell
        containers as attribute values.
    """
    if isinstance(obj, Pointer):
        holder, cell = _get_holder_cell(obj)
        if value is not None:
            if isinstance(value, Container):
                cell.set_container(holder, value)
            else:
                raise TypeError("must be of type container", value)

        return cell.get_container(holder)
    else:
        return CellAgent(obj)
