import sys
from .pointer import SELF
# __pragma__ ('skip')
from .core import CellBase, Container, ResetContainer

__all__ = ("Cell", "MakeCell", "ResetCell", "TypeCell", "MakeTypeCell")
# __pragma__ ('noskip')
# __pragma__ ('ecom')
"""?
from .pcore import CellBase, Container, ResetContainer
?"""
# __pragma__ ('noecom')

_cell_counter = 0


class Cell(CellBase):
    """
    A descriptor to assign cell containers to objects.

    Args:
        default_val: The default value of the cell.
    """
    __container__ = Container  # factory
    __slots__ = ("order", "default")

    def __init__(self, default=None):
        super().__init__()
        global _cell_counter
        self.default = default
        self.order = _cell_counter
        _cell_counter += 1

    def create_container(self, holder):
        return self.__container__(self.default)

    def copy(self):
        r = self.__class__(self.default)
        r.order = self.order
        r.name = self.name
        r.index = self.index
        return r

    def __repr__(self):
        return "<{} {}({}/{})>".format(
            self.__class__.__name__, self.name, self.index,
            self.order)  # pragma: no cover


class MakeCell(Cell):
    """
    A cell that creates the default value with a factory during
    construction of the reactive object.

    Args:
        factory (callable): A factory that uses args and kwargs to
            create the default object.
        *args: argument list for factory
        **kwargs: keyword arguments for factory

    Examples:
        >>> @reactive
        class ListContainer(object):
            values = MakeCell(list, (1, 2, 3))
    """
    __slots__ = ("args", "kwargs")

    def __init__(self, factory, *args, **kwargs):
        super().__init__(factory)
        self.args = args
        self.kwargs = kwargs

    def copy(self):
        r = self.__class__(self.default, *self.args, **self.kwargs)
        r.order = self.order
        r.name = self.name
        r.index = self.index
        return r

    def create_container(self, holder):
        def replace_self(a):
            return holder if a is SELF else a

        args = [replace_self(a) for a in self.args]
        kwargs = dict((k, replace_self(v)) for k, v in self.kwargs.items())
        return Container(self.default(*args, **kwargs))


class ResetCell(Cell):
    """
    A Cell that silently resets it's value after all depending
    rules have been called.
    """
    __container__ = ResetContainer  # factory


class _TypeConverter(object):
    __slots__ = ("converter", )

    def __init__(self, converter):
        self.converter = converter

    def __call__(self, to_convert):
        converted = self.converter(to_convert)
        try:
            self.converter = converted.convert
        except AttributeError:
            pass

        return converted


class TypeCell(Cell):
    """
    A cell the coerces an input cell to the type of its default value.

    Args:
        default_val: The default value of the cell.
        converter (callable): If not None, the converter will be used to
            to coerce any value to the right type. Otherwise
            `type(default_val)` will be used as converter.
    """
    __slots__ = ("converter", )

    def __init__(self, default_val, converter=None):
        super().__init__(default_val)
        if converter is not None:
            self.converter = converter

        elif hasattr(getattr(default_val, "convert", None), '__call__'):
            self.converter = _TypeConverter(default_val.convert)

        else:
            self.converter = type(default_val)

    def __set__(self, holder, value):
        try:
            super().__set__(holder, self.converter(value))
        except BaseException:
            type_, exc, traceback = sys.exc_info()
            exc.args += (self,)
            if sys.version_info[0] >= 3:
                raise exc.with_traceback(traceback)
            else:  # pragma: no cover
                exec("raise exc, None, traceback")


class MakeTypeCell(MakeCell):
    def __set__(self, holder, value):
        super().__set__(holder, self.default(value))
