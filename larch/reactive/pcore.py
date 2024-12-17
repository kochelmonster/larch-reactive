"""
This module contains the core functionality of larch.reactive.
"""
import sys
import warnings
import logging
import operator
from bisect import insort_left
from collections import deque
from functools import reduce, update_wrapper
from weakref import ref

pointer_itemgetter = operator.itemgetter
pointer_attrgetter = operator.attrgetter


# __pragma__ ('ecom')
"""?
class LocalContext:
    pass


class GreenletExit(BaseException):
    pass
?"""

# __pragma__ ('skip')
pointer_attrgetter = type(pointer_attrgetter(""))  # for pypy
try:
    from gevent import GreenletExit
    from gevent.local import local as LocalContext

except ImportError:  # pragma: no cover
    class GreenletExit(BaseException):
        pass

    from threading import local as LocalContext

__all__ = ("rcontext", "CellBase", "ReactiveState", "Subject", "Container",
           "ResetContainer", "Rule", "IterRule", "pointer_attrgetter",
           "pointer_itemgetter", "pointer_resolve", "ReactiveWarning")
# __pragma__ ('noskip')

logger = logging.getLogger("larch.reactive")


def pointer_resolve(root, accessors):
    return reduce(lambda x, y: y(x), accessors, root)


class DecoratorContext:
    """
    A base class for objects that can be used
    as decorators and as contexts.
    """
    __slots__ = ()

    # __pragma__("kwargs")
    def call(self, func, *args, **kwargs):
        with self:
            result = func(*args, **kwargs)
        return result  # transcript bug
    # __pragma__("nokwargs")

    def __call__(self, func):
        # __pragma__("kwargs")
        def handler(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        # __pragma__("nokwargs")

        result = update_wrapper(handler, func)
        result.decorated = func
        return result


class AtomicDecoratorContext(DecoratorContext):
    """
    The atomic decorator context. Rules will be executed at the end of
    the context.
    """

    def __enter__(self):
        rcontext._atomic_start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        rcontext._atomic_end()
        return False


class SilentDecoratorContext(DecoratorContext):
    """
    The silent decorator context. Within this context a change of a cell
    will not trigger any rules.
    """
    __slots__ = ("old_notify", )

    def __enter__(self):
        # the atomic context ensures that silent will not influence
        # other greenlets
        rcontext._atomic_start()
        self.old_notify = rcontext.notify
        rcontext.notify = rcontext._dumy_notify

    def __exit__(self, exc_type, exc_val, exc_tb):
        rcontext.notify = self.old_notify
        rcontext._atomic_end()
        return False


class UntouchedDecoratorContext(DecoratorContext):
    """
    The untouched decorator context. This context makes only sense within
    rules. Within this context no cell will be touched.
    """
    __slots__ = ("old_touch", )

    def __enter__(self):
        self.old_touch = rcontext.touch
        rcontext.touch = rcontext._dumy_touch

    def __exit__(self, exc_type, exc_val, exc_tb):
        rcontext.touch = self.old_touch
        return False


class TouchedDecoratorContext(DecoratorContext):
    """
    The touch decorator context. The context makes only sense within
    a untouched context. Within this context cells will be touched again.
    """
    __slots__ = ("old_touch", )

    def __enter__(self):
        self.old_touch = rcontext.touch
        rcontext.touch = rcontext._touch

    def __exit__(self, exc_type, exc_val, exc_tb):
        rcontext.touch = self.old_touch
        return False


class ReactiveWarning(UserWarning):
    pass


class ReactiveContext(LocalContext):
    """
    A ReactiveContext is the core driver for reactive behaviour.
    It manages the subject - observer relation between cells and rules,
    and cares for the execution order of rules.

    Only one ReativeContext exists in a program that can be accessed by:

    >>> larch.reactive.rcontext
    """

    def __init__(self):
        self.atomic_count = 0
        self.atomic_start_round = 0
        self._call_counter = 0
        self.current_observer = None
        self.touch = self._dumy_touch
        self.notify = self._notify

        self.old_values = {}
        # the subject values before an atomic operation.

        self.observers = []
        # all observers in the active atomic operation in their call order

        self.observer_count = {}
        # how often is one observer in the observers list

        self.callbacks = deque()
        # sequence of all callbacks to notify the end of notification process,
        # transformed from set to list to keep the callbacks order.

        self.atomic = AtomicDecoratorContext()

    @property
    def untouched(self):
        """UntouchedDectoratorContext: a new context."""
        return UntouchedDecoratorContext()

    @property
    def touched(self):
        """TouchedDecoratorContext: a new context."""
        return TouchedDecoratorContext()

    @property
    def silent(self):
        """SilentDecoratorContext: a new context."""
        return SilentDecoratorContext()

    @property
    def rounds(self):
        """int: the count of atomic operations, since program start."""
        return self.atomic_start_round

    @property
    def transaction_level(self):
        """int: count of recursive atomic operations."""
        return self.atomic_count

    @property
    def inside_rule(self):
        """bool: `True` if the current frame is inside a rule."""
        return self.current_observer

    @property
    def inside_touch(self):
        """bool: `True` if the current frame is inside a touch context."""
        return self.touch == self._touch

    def _atomic_start(self):
        self.atomic_start_round = self._call_counter
        self.atomic_count += 1

    def _atomic_end(self):
        if self.atomic_count != 1:
            self.atomic_count -= 1
            return

        # self.atomic_count == 1
        observers = self.observers
        observer_count = self.observer_count
        greenlet_exit = False

        # execute rules
        try:
            # a "for o in observers" loop is not possible
            # observer.notify() can change new cells and modify
            # the observers list
            # the following lines correctly run the testcases
            # test_renew_cell and test_one_run in test_reactive.py

            for i in range(10000):  # avoid an infinite loop
                # __pragma__ ('tconv')
                if not observers:
                    observer_count.clear()
                    break
                # __pragma__ ('notconv')

                # observers are sorted in reverse order
                observer = observers.pop()
                key_observer = id(observer)
                if observer_count[key_observer] <= 1:
                    del observer_count[key_observer]
                    try:
                        observer.notify()
                    except GreenletExit:
                        greenlet_exit = True
                        logger.exception(
                            "GreenletExit during observer notification", stack_info=True)
                else:
                    # this observer occurs multiple times. Only call the
                    # latest occurence
                    observer_count[key_observer] -= 1
            else:
                self.callbacks.clear()
                exp = RuntimeError("possible endless recursion {0}".format(observers))
                del observers[:]
                observer_count.clear()
                raise exp
        finally:
            self.atomic_count = 0
            self.active_greenlet = None
            self.old_values.clear()

        greenlet_exit = self._execute_callbacks(greenlet_exit)
        if greenlet_exit:
            raise GreenletExit()

    def _execute_callbacks(self, greenlet_exit):
        callbacks = self.callbacks
        self.callbacks = deque()
        for c in callbacks:
            try:
                c()
            except Exception as e:
                # __pragma__ ('skip')
                exc_type, exc_value, tb = sys.exc_info()
                from .exception import format_full_exception_tb
                tb = format_full_exception_tb()
                msg = 'Exception while executing callback: "{0}"\n{1}'
                warnings.warn(msg.format(exc_value, tb), ReactiveWarning)
                logger.exception("Exception while executing callback %r: %r", c, e, stack_info=True)
                # __pragma__ ('noskip')
                """?
                console.trace("Exception while executing callback", repr(e), repr(c), e.stack)
                ?"""
            except GreenletExit:
                greenlet_exit = True
                logger.exception("GreenletExit while executing callback %r", c, stack_info=True)

        return greenlet_exit

    def rule_call(self, rule, args, kwargs):
        old_touch = self.touch
        old_observer = self.current_observer
        self.current_observer = rule
        self.touch = self._touch
        try:
            rule.__call__(args, kwargs)
        except GreenletExit:
            raise
        except BaseException as e:
            # __pragma__ ('skip')
            exc_type, exc_value, tb = sys.exc_info()
            from .exception import format_full_exception_tb
            tb = format_full_exception_tb()
            msg = 'Exception while calling rule "{0}({1!r}, {2!r})": "{3!r}"\n{4}'
            warnings.warn(msg.format(rule, args, kwargs, exc_value, tb), ReactiveWarning)
            logger.exception("Exception while calling rule %r", e, stack_info=True)
            # __pragma__ ('noskip')
            """?
            console.trace("Exception while calling rule", repr(e), repr(rule), e.stack)
            ?"""

        finally:
            self.touch = old_touch
            self.current_observer = old_observer

    def _notify(self, subject, old_value):
        id_subject = id(subject)
        self.old_values.setdefault(id_subject, old_value)
        self.emit(subject.get_observers())
        subject.clear_observers()

    def _dumy_notify(self, subject, old_value):
        pass

    def emit(self, observers):
        my_observers = self.observers
        my_observer_count = self.observer_count
        for o in observers:
            insort_left(my_observers, o)
            ko = id(o)
            my_observer_count[ko] = my_observer_count.get(ko, 0) + 1

    def push_callback(self, callback):
        self.callbacks.append(callback) if self.transaction_level else callback()

    def shift_callback(self, callback):
        self.callbacks.appendleft(callback) if self.transaction_level else callback()

    def call_counter(self):
        self._call_counter += 1
        return self._call_counter

    def _touch(self, subject):
        subject.add_observer(self.current_observer)
        return True

    def _dumy_touch(self, subject):
        return False


rcontext = ReactiveContext()


class Observer:
    level = 0
    __slots__ = ("last_call", )

    def notify(self, initial=False):
        pass  # pragma: no cover

    def __lt__(self, other):
        # observers are sorted in reverse order!
        return (self.level > other.level
                or self.level == other.level and self.last_call > other.last_call)

    def __eq__(self, other):
        return self.level == other.level and self.last_call == other.last_call


class IterRule(Observer):
    """A Rule represents a `rule` instance method of a reactive class"""
    __slots__ = ("level", "method", "holder", "__weakref__")

    def __init__(self, holder, method, level, last_call):
        self.holder = holder
        self.method = method
        self.level = level
        self.last_call = last_call

    def notify(self, args=(), kwargs={}):
        self.last_call = rcontext.call_counter()
        rcontext.rule_call(self, args, kwargs)

    def __repr__(self):
        if self.holder() is None:
            return (f"<Rule obsolete {self.method.__name__} "
                    f"({self.level}, {self.last_call})>")

        return (f"<Rule {self.method.__name__}({self.level}, "
                f"{self.last_call}) of {self.holder()!r}>")

    def __call__(self, args, kwargs):
        holder = self.holder()
        if holder is not None:
            iterator = self.method(holder, *args, **kwargs)

            def call_iterator():
                try:
                    next(iterator)
                    rcontext.push_callback(call_iterator)
                except StopIteration:
                    pass
                except RuntimeError as e:
                    if e.args != ('generator raised StopIteration',):
                        raise

            call_iterator()  # __: skip
            """?
            if iterator:
                call_iterator()
            ?"""


# __pragma__ ('skip')
class Rule(IterRule):
    def __call__(self, args, kwargs):
        holder = self.holder()
        if holder is not None:
            try:
                self.method(holder, *args, **kwargs)
            except StopIteration:
                pass
# __pragma__ ('noskip')


class Subject:
    """
    An observer's subject
    """

    __slots__ = ("_observers", "_last_counter")

    def __init__(self):
        self._observers = {}
        """
        A set of observers that will be called when the subjects value changes.
        """

        self._last_counter = 0
        """
        The variable is used to check if a observer still depends on this
        subject if observer.last_call > self._last_counter ==> the observer
        does not depend anymore.
        (see TestReactive.test_decouple of test_reactive.py)
        """

    def touch(self):
        rcontext.touch(self)

    def changed(self, old_value=None):
        # __pragma__ ('tconv')
        if self._observers:
            rcontext.atomic.call(rcontext.notify, self, old_value)
        # __pragma__ ('notconv')

    def take(self, other):
        """takes over the attributes of another subject"""
        self._observers.update(other._observers)
        self._last_counter = max(self._last_counter, other._last_counter)

    def get_observers(self):
        """Returns the subject's observers"""
        return self.filter_observers(self._observers.values())

    def filter_observers(self, observers):
        last_counter = self._last_counter
        observers = (o() for o in observers)
        return [o for o in observers if o is not None and o.last_call <= last_counter]

    def add_observer(self, observer):
        if observer:
            self._last_counter = max(observer.last_call, self._last_counter)
            self._observers[id(observer)] = ref(observer)

    def clear_observers(self):
        self._observers = {}


def _cell_to_container(reactive):
    return [c.create_container(reactive) for c in reactive.__reactive_cells__.values()]


class _NOVAL:
    pass


def _state_from_dict(state, reactive, dict_):
    for c in reactive.__reactive_cells__.values():
        val = dict_.get(c.name, _NOVAL)
        if val is not _NOVAL:
            state[c.index]._value = val


def _state_as_dict(state, reactive):
    result = {}
    for c in reactive.__reactive_cells__.values():
        result[c.name] = state[c.index]._value
    return result


# __pragma__ ('skip')
class ReactiveState(list):
    """The state of a reactive objects. Contains all cell container."""

    def __init__(self, reactive):
        self[:] = _cell_to_container(reactive)

    def from_dict(self, reactive, dict_):
        _state_from_dict(self, reactive, dict_)

    def as_dict(self, reactive):
        return _state_as_dict(self, reactive)
# __pragma__ ('noskip')


"""?
__pragma__("js", "{}", '''

var ReactiveState_ = function(reactive) {
    this.push.apply(this, _cell_to_container(reactive));
    return this
}
ReactiveState_.prototype = Object.create(Array.prototype);
ReactiveState_.prototype.from_dict = function(reactive, dict_) {
  _state_from_dict(this, reactive, dict_);
}
ReactiveState_.prototype.as_dict = function(reactive) {
  return _state_as_dict(this, reactive);
}

export var ReactiveState = function(reactive) {
    return new ReactiveState_(reactive);
}

ReactiveState_.prototype.__class__ = ReactiveState;
deque.__name__ = 'ReactiveState';
deque.__bases__ = [list];
''')
?"""


class Container(Subject):
    """A cell container that stores a cell's value."""
    __slots__ = ("_value", )

    def __init__(self, value):
        super().__init__()
        self._value = value
        # see ccore.pyx Container.__dealloc__
        rcontext.old_values.pop(id(self), None)

    def set_value(self, value):
        """Sets the containers value."""
        old_value = self._value
        self._value = value
        # __pragma__ ("opov")
        if old_value != value or type(old_value) != type(value):
            # __pragma__ ("noopov")
            self.changed(old_value)
            return True
        return False

    def get_value(self):
        """Returns the container's value"""
        self.touch()
        return self._value

    def __repr__(self):
        return "<{0}({1:x}): {2!r}>".format(self.__class__.__name__, id(self),
                                            self._value)


class ResetContainer(Container):
    def __init__(self, value):
        super().__init__(value)
        self._reset_value = value

    def set_value(self, value):
        old_value = self._value
        self._value = value
        if old_value != value or type(old_value) != type(value):
            def reset():
                self._value = self._reset_value

            with rcontext.atomic:
                self.changed(self._reset_value)
                rcontext.shift_callback(reset)
            return True
        return False


class CellBase:
    """A descriptor to assign cell containers to objects."""
    __slots__ = ("name", "index")
    __container__ = Container  # factory

    def __init__(self):
        self.name = None
        self.index = -1

    def __init_cell__(self, name, index):
        self.name = name
        self.index = index

    def __get__(self, holder, owner):
        if holder is None:
            return self

        return holder.__reactive_state__[self.index].get_value()

    def __set__(self, holder, value):
        holder.__reactive_state__[self.index].set_value(value)

    def get_container(self, holder):
        return holder.__reactive_state__[self.index]

    def set_container(self, holder, value):
        # if we replace the container we have to keep the rules
        value.take(self.get_container(holder))
        holder.__reactive_state__[self.index] = value
# __pragma__ ('noecom')
