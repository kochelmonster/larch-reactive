# cython: language_level = 3
# distutils: language = c++
import types
import sys
import warnings
import logging
from functools import update_wrapper
from cpython cimport (
    Py_INCREF, Py_DECREF, PyThread_get_thread_ident, PyList_GET_ITEM,
    PyObject_GetAttrString, PyBytes_AS_STRING, PyObject)
from cpython.tuple cimport PyTuple_GET_ITEM, PyTuple_SET_ITEM, PyTuple_New
from cpython.weakref cimport PyWeakref_GET_OBJECT, PyWeakref_NewRef
from cython.operator cimport dereference as deref, preincrement as inc
from libcpp.deque cimport deque
from ._handler import _make_handler

cdef extern from "pyref.h":
    cdef cppclass PyRef:
        PyRef(PyObject* ref_)
        PyObject* ref


cdef logger = logging.getLogger("larch.reactive")

#some gevent support
cdef extern from "greenlet.h":
    ctypedef PyObject PyGreenlet

    PyGreenlet* PyGreenlet_GetCurrent()
    void PyGreenlet_Import()


ctypedef long (*get_fiber_id_t)()
cdef get_fiber_id_t get_current_fiber_id

ctypedef object (*get_fiber_t)()
cdef get_fiber_t get_current_fiber


cdef c_current_thread = None

cdef object get_current_thread():
    return c_current_thread()

cdef long get_current_greenlet_id():
    cdef PyGreenlet* g = PyGreenlet_GetCurrent()
    Py_DECREF(<object>g)
    return <long>g


try:
    from greenlet import GreenletExit, getcurrent
except ImportError:
    from threading import current_thread

    class GreenletExit(BaseException):
        pass

    c_current_thread = current_thread
    get_current_fiber = get_current_thread
    get_current_fiber_id = <get_fiber_id_t>PyThread_get_thread_ident
else:
    PyGreenlet_Import()

    get_current_fiber = <get_fiber_t>PyGreenlet_GetCurrent
    get_current_fiber_id = get_current_greenlet_id


__all__ = ("rcontext", "CellBase", "ReactiveState", "Subject", "Container",
           "Rule", "IterRule", "ResetContainer", "pointer_attrgetter",
           "pointer_itemgetter", "pointer_resolve", "ReactiveWarning")


cdef class Subject
cdef class Observer
cdef class Rule
cdef class Container
cdef class ReactiveContext
cdef class ReactiveState
cdef class CellBase


cdef class DecoratorContext:
    def call(self, func, *args, **kwargs):
        with self:
            return func(*args, **kwargs)

    def __call__(self, func):
        result = update_wrapper(_make_handler(self, func), func)
        result.decorated = func
        return result


cdef class AtomicDecoratorContext(DecoratorContext):
    def __enter__(self):
        ircontext._atomic_start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        ircontext._atomic_end()
        return False


cdef class SilentDecoratorContext(DecoratorContext):
    cdef int old_do_notify

    def __enter__(self):
        cdef _ContextVars v = ircontext._vars()
        ircontext._atomic_start()
        self.old_do_notify = v.do_notify
        v.do_notify = 0

    def __exit__(self, exc_type, exc_val, exc_tb):
        ircontext._vars().do_notify = self.old_do_notify
        ircontext._atomic_end()
        return False


cdef class UntouchedDecoratorContext(DecoratorContext):
    cdef int old_do_touch

    def __enter__(self):
        cdef _ContextVars v = ircontext._vars()
        self.old_do_touch = v.do_touch
        v.do_touch = 0

    def __exit__(self, exc_type, exc_val, exc_tb):
        ircontext._vars().do_touch = self.old_do_touch
        return False


cdef class TouchedDecoratorContext(DecoratorContext):
    cdef int old_do_touch

    def __enter__(self):
        cdef _ContextVars v = ircontext._vars()
        self.old_do_touch = v.do_touch
        v.do_touch = 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        ircontext._vars().do_touch = self.old_do_touch
        return False


ctypedef deque[PyRef] ObjectDeque
ctypedef deque[PyRef].iterator ObjectDequeIter


cdef class _ContextVars:
    cdef:
        public long atomic_start_round
        public long _call_counter
        public int atomic_count
        public object current_observer
        public int do_touch
        public int do_notify
        public dict old_values
        public list observers
        public dict observer_count
        ObjectDeque* callbacks

    def __init__(self):
        #for a documentation of the attributes
        #see pcore.py
        self.atomic_start_round = 0
        self.atomic_count = 0
        self._call_counter = 0
        self.current_observer = None
        self.do_touch = <int> 0
        self.do_notify = <int>1
        self.old_values = {}
        self.observers = []
        self.observer_count = {}
        self.callbacks = new ObjectDeque()

    def __dealloc__(self):
        del self.callbacks


class ReactiveWarning(UserWarning):
    pass


cdef class ReactiveContext:
    cdef:
        public AtomicDecoratorContext atomic
        long _last_fiber_id
        _ContextVars _current_vars

    def __init__(self):
        self.atomic = AtomicDecoratorContext()
        self._last_fiber_id = 0

    cpdef _ContextVars _vars(self):
        cdef long fiber_id = get_current_fiber_id()

        if fiber_id == self._last_fiber_id:
            return self._current_vars

        self._last_fiber_id = fiber_id
        fiber = get_current_fiber()

        rvars = getattr(fiber, "__larch_reactive_vars__", None)
        if rvars is None:
            rvars = fiber.__larch_reactive_vars__ = _ContextVars()

        self._current_vars = <_ContextVars>rvars
        return self._current_vars

    property observers:
        def __get__(self):
            return self._vars().observers

    property old_values:
        def __get__(self):
            return self._vars().old_values

    property untouched:
        def __get__(self):
            return UntouchedDecoratorContext()

    property touched:
        def __get__(self):
            return TouchedDecoratorContext()

    property silent:
        def __get__(self):
            return SilentDecoratorContext()

    property rounds:
        def __get__(self):
            return self._vars().atomic_start_round

    property transaction_level:
        def __get__(self):
            return self._vars().atomic_count

    property inside_rule:
        def __get__(self):
            return self._vars().current_observer

    property inside_touch:
        def __get__(self):
            cdef _ContextVars x = self._vars()
            return bool(x.do_touch)

    cpdef int _atomic_start(self) except -1:
        cdef _ContextVars x = self._vars()
        x.atomic_start_round = x._call_counter
        x.atomic_count += 1
        return 0

    cpdef int _atomic_end(self) except -1:
        cdef:
            list observers
            dict observer_count
            Observer observer
            _ContextVars x = self._vars()
            size_t count
            int greenlet_exit = 0

        if x.atomic_count != 1:
          x.atomic_count -= 1
          return 0

        observer_count = x.observer_count
        observers = x.observers

        try:
          for i in range(10000):
              if not observers:
                  break
              observer = observers.pop()

              count = observer_count.get(observer, 0)
              if count <= 1:
                  del observer_count[observer]
                  try:
                      observer.notify()
                  except GreenletExit:
                      greenlet_exit = 1
                      logger.exception(
                          "GreenletExit during observer notification",
                          stack_info=True)
              else:
                  observer_count[observer] = count - 1
          else:
              x.callbacks.clear()
              exp = RuntimeError("possible endless recursion {0}".format(observers))
              del observers[:]
              observer_count.clear()
              raise exp
        finally:
          x.old_values.clear()
          x.atomic_count = 0

        if not x.callbacks.empty():
            greenlet_exit = self._execute_callbacks(x, greenlet_exit)

        if greenlet_exit:
          raise GreenletExit()

        return 0

    cdef int _execute_callbacks(self, _ContextVars x,
                                int greenlet_exit) except -1:
        cdef:
            ObjectDeque* callbacks
            ObjectDequeIter it

        callbacks = x.callbacks
        x.callbacks = new ObjectDeque()

        it = callbacks.begin()
        while it != callbacks.end():
            c = <object>deref(it).ref
            inc(it)
            try:
                c()
            except Exception as e:
                from .exception import format_full_exception_tb
                tb = format_full_exception_tb()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                warnings.warn(
                    'Exception while executing callback: "{0}"\n{1}'.format(
                        exc_value, tb), ReactiveWarning)
                logger.exception("Exception while executing callback %r: %r",
                                  c, e, stack_info=True)
            except GreenletExit:
                greenlet_exit = 1
                logger.exception("GreenletExit while executing callback %r", c, stack_info=True)

        del callbacks
        return greenlet_exit

    cpdef int rule_call(self, Rule rule, args, kwargs) except -1:
        cdef _ContextVars x = self._vars()
        old_do_touch = x.do_touch
        old_observer = x.current_observer
        x.current_observer = rule
        x.do_touch = 1
        try:
            rule.call_method(args, kwargs)
        except GreenletExit:
            raise
        except BaseException as e:
            from .exception import format_full_exception_tb
            tb = format_full_exception_tb()
            exc_type, exc_value, exc_traceback = sys.exc_info()
            msg = ('Exception while calling rule "{0}({1!r}, {2!r})": "{3!r}"\n{4}')
            warnings.warn(msg.format(rule, args, kwargs, exc_value, tb), ReactiveWarning)
            logger.exception("Exception while calling rule %r", e, stack_info=True)
        finally:
            x.do_touch = old_do_touch
            x.current_observer = old_observer

    cpdef int notify(self, Subject subject, old_value) except *:
        cdef _ContextVars x = self._vars()
        if x.do_notify:
            subject_id = id(subject)
            x.old_values.setdefault(subject_id, old_value)
            self.emit(subject.get_observers())
            subject.clear_observers()

    cpdef int emit(self, list observers) except *:
        cdef:
            _ContextVars x = self._vars()
            size_t count

        for o in observers:
            insort_left(x.observers, o)
            count = x.observer_count.get(o, 0)
            x.observer_count[o] = count + 1

    cpdef int push_callback(self, callback) except -1:
        cdef _ContextVars x = self._vars()
        if x.atomic_count:
            x.callbacks.push_back(PyRef(<PyObject*>callback))
        else:
            callback()

    cdef int shift_callback(self, callback) except -1:
        cdef _ContextVars x = self._vars()
        if x.atomic_count:
            x.callbacks.push_front(PyRef(<PyObject*>callback))
        else:
            callback()

    cpdef long call_counter(self):
        cdef _ContextVars x = self._vars()
        x._call_counter += 1
        return x._call_counter

    cpdef object touch(self, Subject subject):
        cdef _ContextVars x = self._vars()
        if x.do_touch:
            subject.add_observer(x.current_observer)
            return True

        return False


cdef ReactiveContext ircontext = ReactiveContext()
rcontext = ircontext


def null_func():
    pass


cdef class Observer:
    cdef:
        public size_t last_call
        public int level

    cpdef notify(self):
        pass

    def __hash__(self):
        return <int><long><PyObject*>self

    cdef int is_less(self, Observer other):
        # reverse
        return (self.level > other.level
                or self.level==other.level and self.last_call > other.last_call)


cdef class Rule(Observer):
    """A rule that depends on cells an manipulate cells"""
    cdef public object holder
    cdef public method
    cdef object __weakref__

    def __init__(self, holder, method, level, last_call):
        self.holder = holder
        self.method = method
        self.last_call = last_call
        self.level = level

    cdef int call_method(self, args, kwargs) except -1:
        holder = <object>PyWeakref_GET_OBJECT(self.holder)
        if holder is not None:
            try:
                self.method(holder, *args, **kwargs)
            except StopIteration:
                pass

    cpdef notify(self, args=(), kwargs={}):
        self.last_call = ircontext.call_counter()
        ircontext.rule_call(self, args, kwargs)

    def __repr__(self):
        holder = <object>PyWeakref_GET_OBJECT(self.holder)
        if holder is None:
            return "<Rule obsolete {0} ({1}, {2})>".format(
                self.method.__name__, self.level, self.last_call)

        return "<Rule {0}({1}, {2}) of {3!r}>".format(
            self.method.__name__, self.level, self.last_call, self.holder())


cdef class _IterCaller:
    cdef object iterator

    def __init__(self, iterator):
        self.iterator = iterator

    def call(self):
        try:
            next(self.iterator)
            rcontext.push_callback(self.call)
        except StopIteration:
            pass
        except RuntimeError as e:
            if e.args != ('generator raised StopIteration',):
                raise


cdef class IterRule(Rule):
    cdef int call_method(self, args, kwargs) except -1:
        cdef _IterCaller caller
        holder = <object>PyWeakref_GET_OBJECT(self.holder)
        if holder is not None:
            iterator = self.method(holder, *args, **kwargs)
            caller = _IterCaller(iterator)
            caller.call()


cdef class Subject:
    """An observer's subject"""
    cdef public dict _observers
    cdef public size_t _last_counter

    def __init__(self):
        self._observers = {}
        self._last_counter = 0

    cpdef int touch(self):
        ircontext.touch(self)

    cpdef int changed(self, object old_value=None) except -1:
        if self._observers:
            ircontext._atomic_start()
            ircontext.notify(self, old_value)
            ircontext._atomic_end()

        return 0

    cpdef int take(self, Subject other):
        self._observers.update(other._observers)
        self._last_counter = max(self._last_counter, other._last_counter)

    cpdef list get_observers(self):
        return self.filter_observers(self._observers)

    cdef list filter_observers(self, dict observers):
        cdef:
            size_t last_counter = self._last_counter
            Observer o
            list result = []

        for r in observers.values():
            o = <Observer>PyWeakref_GET_OBJECT(r)
            if o is not None and o.last_call <= last_counter:
                result.append(o)

        return result

    cpdef int add_observer(self, Observer observer) except -1:
        if observer:
            self._last_counter = max(observer.last_call, self._last_counter)
            self._observers[id(observer)] = PyWeakref_NewRef(observer, None)
        return 0

    cpdef int clear_observers(self) except -1:
        self._observers = {}
        return 0


cdef class ReactiveState:
    cdef tuple containers

    def __init__(self, reactive):
        cdef:
            CellBase c
            dict cells = reactive.__reactive_cells__

        self.containers = <tuple>PyTuple_New(len(cells))
        for c in cells.values():
            tmp = c.create_container(reactive)
            Py_INCREF(tmp)
            PyTuple_SET_ITEM(self.containers, c.index, tmp)

    cdef void replace_container(self, int index, Container container):
        cdef Container tmp = <Container>self.get(index)
        Py_DECREF(tmp)
        Py_INCREF(container)
        PyTuple_SET_ITEM(self.containers, index, container)

    cdef inline Container get(self, int index):
        return <Container>PyTuple_GET_ITEM(self.containers, index)

    def from_dict(self, reactive, state):
        cdef:
            CellBase c
            Container tmp
            dict cells = reactive.__reactive_cells__

        for c in cells.values():
            if c.name in state:
                self.get(c.index)._value = state.get(c.name)

    def as_dict(self, reactive):
        cdef:
            CellBase c
            Container tmp
            dict cells = reactive.__reactive_cells__

        result = {}
        for c in cells.values():
            result[c.name] = self.get(c.index)._value

        return result


cdef class Container(Subject):
    """A cell container that actually contains the value"""
    cdef public object _value

    def __init__(self, value):
        super(Container, self).__init__()
        self._value = value
        #A destroyed container can be recreated (i.e. it has the same id)
        #in the same atomic round providing a wrong old_value for
        #the new (recreated) Container leading to wrong behaviour
        ircontext._vars().old_values.pop(id(self), None)

    cpdef int set_value(self, object value) except *:
        cdef object old_value = self._value
        self._value = value
        if old_value != value or type(old_value) != type(value):
            self.changed(old_value)
            return 1
        return 0

    cpdef object get_value(self):
        self.touch()
        return self._value

    def __repr__(self):
        return "<{0}({1:x}: {2!r}>".format(
            self.__class__.__name__, id(self), self._value)


cdef class _ResetValue:
    cdef public Container dest
    cdef public object old_value

    def __cinit__(self, dest, old_value):
        self.dest = dest
        self.old_value = old_value

    cpdef reset(self):
        self.dest._value = self.old_value


cdef class ResetContainer(Container):
    cdef public object _reset_value

    def __init__(self, value):
        super(ResetContainer, self).__init__(value)
        self._reset_value = value

    cpdef int set_value(self, value) except *:
        cdef:
            _ResetValue r
            object old_value = self._value

        self._value = value
        if old_value != value or type(old_value) != type(value):
            r = _ResetValue(self, self._reset_value)
            ircontext._atomic_start()
            self.changed(self._reset_value)
            ircontext.shift_callback(r.reset)
            ircontext._atomic_end()
            return 1

        return 0

cdef class CellBase:
    cdef public int index
    cdef public object name

    def __init__(self):
        self.name = ""

    def __init_cell__(self, name, index):
        self.name = name
        self.index = index

    def __get__(self, object holder, object owner):
        cdef ReactiveState state

        if holder is None:
            return self

        state = holder.__reactive_state__
        return state.get(self.index).get_value()

    def __set__(self, object holder, object value):
        cdef ReactiveState state = holder.__reactive_state__
        state.get(self.index).set_value(value)

    cpdef object get_container(self, object holder):
        cdef ReactiveState state = holder.__reactive_state__
        return state.get(self.index)

    cpdef int set_container(self, object holder, object value):
        #if we replace the container we have to keep the rules
        cdef ReactiveState state = holder.__reactive_state__
        value.take(state.get(self.index))
        state.replace_container(self.index, value)


cdef class pointer_accessor:
    cdef object get(self, obj):
        return None

    def __call__(self, obj):
        return self.get(obj)


cdef inline bytes to_bytes3(name):
    return bytes(name, "utf-8")

cdef inline bytes to_bytes2(name):
    return bytes(name)

ctypedef bytes (*to_bytes_t)(name)
cdef to_bytes_t to_bytes

try:
    to_bytes3("t")
except TypeError:
    to_bytes = to_bytes2
else:
    to_bytes = to_bytes3


cdef class pointer_attrgetter(pointer_accessor):
    cdef public bytes name

    def __init__(self, name):
        self.name = to_bytes(name)

    cdef object get(self, obj):
        cdef char* name = PyBytes_AS_STRING(self.name)
        return PyObject_GetAttrString(obj, name)


cdef class pointer_itemgetter(pointer_accessor):
    cdef public index

    def __init__(self, index):
        self.index = index

    cdef object get(self, obj):
        return obj[self.index]


def pointer_resolve(obj, tuple accessors):
    cdef pointer_accessor a

    for a in accessors:
        obj = a.get(obj)

    return obj


cdef insort_left(list olist, Observer item):
    cdef:
        size_t lo = 0
        size_t hi = len(olist)
        size_t mid
        Observer litem
        int res

    while lo < hi:
        mid = (lo + hi) >> 1
        litem = <Observer>PyList_GET_ITEM(olist, mid)
        if litem.is_less(item):
            lo = mid + 1
        else:
            hi = mid

    olist.insert(lo, item)
