"""
Provides reactive collections
"""
from .core import ResetContainer


class MutableObserver(object):
    __slots__ = ("__action_start__", "__action_end__")

    def __init__(self):
        self.__action_start__ = ResetContainer(())
        self.__action_end__ = ResetContainer(())

    def __call__(self, value, method, *args, **kwargs):
        self.__action_start__.set_value(value)
        method(*args, **kwargs)
        self.__action_end__.set_value(value)


def _normalize_slice(list_, slice_):
    def normalize(index, default):
        if index is None:  # pragma: no cover
            index = default

        if index < 0:
            index += len(list_)

        return max(0, min(len(list_), index))

    return slice(normalize(slice_.start, 0), normalize(slice_.stop, len(list_)))


class ListBase(list):
    """
    The base list class which informs dependent rules if the list changes.
    """
    __slots__ = ("__observer__",)

    def __delitem__(self, key):
        if not isinstance(key, slice):
            key = slice(key, key + 1)

        key = _normalize_slice(self, key)
        if key.start >= len(self):
            # nothing to do
            return

        k = ("delete", key)
        self.__observer__(k, super(ListBase, self).__delitem__, key)

    def __delslice__(self, i, j):  # pragma: no cover
        self.__delitem__(slice(i, j))

    def remove(self, value):
        del self[self.index(value)]

    def __setitem__(self, key, value):
        if not isinstance(key, slice):
            if key < 0:
                key = len(self) + key

            key = slice(key, key + 1)
            value = [value]
        else:
            key = _normalize_slice(self, key)

        if not value:
            k = ("delete", key)
            if key.start == key.stop or key.start >= len(self):
                return  # no change at all
        else:
            k = ("change", (key, value))

        self.__observer__(k, super(ListBase, self).__setitem__, key, value)

    def __setslice__(self, i, j, value):  # pragma: no cover
        self.__setitem__(slice(i, j), value)

    def append(self, value):
        self.__observer__(("insert", (len(self), value)), super(ListBase, self).append, value)

    def insert(self, index, value):
        self.__observer__(("insert", (index, value)), super(ListBase, self).insert, index, value)

    def extend(self, value):
        self.__observer__(("extend", value), super(ListBase, self).extend, value)

    def pop(self, index=-1):
        if index < 0:
            index += len(self)

        value = self[index]
        self.__observer__(("delete", slice(index, index + 1)), super(ListBase, self).pop, index)
        return value

    def __iadd__(self, value):
        self.__observer__(("extend", value), super(ListBase, self).__iadd__, value)
        return self

    def __imul__(self, value):
        self.__observer__(("imul", value), super(ListBase, self).__imul__, value)
        return self

    def reverse(self):
        self.__observer__(("order", "reverse"), super(ListBase, self).reverse)

    def sort(self, *args, **kwargs):
        self.__observer__(("order", "sort"), super(ListBase, self).sort, *args, **kwargs)


class List(ListBase):
    """
    A list class which informs dependent rules before the list
    changes and after the change.
    """
    __slots__ = ("__observer__",)

    def __new__(cls, *args, **kwargs):
        obj = super(List, cls).__new__(cls, *args, **kwargs)
        obj.__observer__ = MutableObserver()
        return obj

    @property
    def __action_start__(self):
        return self.__observer__.__action_start__.get_value()

    @property
    def __action_end__(self):
        return self.__observer__.__action_end__.get_value()

    # __getsate__/__setstate__ to avoid __observer__ is pickled
    def __getstate__(self):
        return None

    def __setstate__(self, state):
        pass


class Dict(dict):
    __slots__ = ("__observer__",)

    def __new__(cls, *args, **kwargs):
        obj = super(Dict, cls).__new__(cls, *args, **kwargs)
        obj.__observer__ = MutableObserver()
        return obj

    @property
    def __action_start__(self):
        return self.__observer__.__action_start__.get_value()

    @property
    def __action_end__(self):
        return self.__observer__.__action_end__.get_value()

    # __getsate__/__setstate__ to avoid __observer__ is pickled
    def __getstate__(self):
        return None

    def __setstate__(self, state):
        pass

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)

        self.__observer__(("delete", key), super(Dict, self).__delitem__, key)

    def __setitem__(self, key, value):
        self.__observer__(("change", (key, value)),
                          super(Dict, self).__setitem__, key, value)

    def setdefault(self, key, default=None):
        if key not in self:
            self.__observer__(("change", (key, default)),
                              super(Dict, self).__setitem__, key, default)
        return self[key]

    def update(self, *args, **kwargs):
        self.__observer__(("update", (args, kwargs)),
                          super(Dict, self).update, *args, **kwargs)

    def popitem(self):
        for r in self.items():
            del self[r[0]]
            return r

        raise KeyError("empty")

    def pop(self, key, *args):
        if key in self:
            r = self[key]
            del self[key]
            return r

        if args:
            return args[0]

        raise KeyError(key)

    def clear(self):
        self.__observer__(("clear", None), super(Dict, self).clear)
