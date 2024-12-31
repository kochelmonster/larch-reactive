.. |ra| replace:: `larch.reactive`
.. |bend| image:: db.gif
  :width: 1em

Larch-Reactive by Examples
==========================

This chapter introduces every feature of |ra|, by providing an example.
Sections marked with |bend| describe the internals of |ra| and can be skipped.
But keep in mind, if you want to get a real deep insight view: read the code.

.. _firstuc:

Creating Reactive Classes, Cells, Rules
---------------------------------------

Lets come back to the first example. |ra| implements the observer pattern to
connect rules (observer) to cells (subject).

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start example1>
    :end-before: # <end example1>
    :linenos:

Line 4:
  The :func:`~larch.reactive.reactive` decorator transforms an "ordinary" python
  class to a "reactive" class.

Lines 6-10:
  Attributes that can be watched by rules must be declared as
  :class:`~larch.reactive.Cell`. A Cell can have a default value by providing
  an argument while construction. By default cells are initialized with `None`.

Line 12, 17:
  The :func:`~larch.reactive.rule` decorator transforms an "ordinary" python
  method to a rule, that is able to observe cells.
  Whenever a rule is executed, reading a cell's value, registers the rule
  as observer for that cell. When such a cell changes its value, the rule is
  executed again.

Line 24:
  Cells can be initialized by using keyword arguments, while constructing a
  reactive object.

  |ra| extends the class `__init__` and add the following functionality:

  1. For each cell a `Container` is created, that stores
     the cell's value and acts as subject.

  2. For each rule an `Observer` object is created calling the rule method, when
     the observer is notified.

  3. All rules are executed for the first time in their order of appearance.

Line 31:
  Changing a cells value will execute all rules observing the cell.


.. _bestpractice:
.. note::

  After several years of using the |ra|-library some best practice clues
  have been evolved:

  - keep rules short
  - try to avoid calling functions. Often this can lead to hidden dependencies,
    if the function accidently read unwanted cells. If you have to call
    function use the :ref:`yield mechanism<yield_rules>`.


|bend| Internals of `write`
...........................

The following diagramm shows the internal state of `write` at line 34. (For more
in depth information read the code in pcore.py)

.. uml::

  object "write:Task" as write {
    __reactive_state__ = [...]
    __reactive_rules__ = (...)
  }

  object "read:Task" as read {
    __reactive_state__ = [...]
    __reactive_rules__ = (...)
  }

  object "end:Container" as rend {
    value=datetime(2016, 1, 9, 14)
  }

  object "start:Container" as start {
    value=datetime(2016, 1, 9, 11)
  }

  object "end:Container" as end {
    value=datetime(2016, 1, 9, 14)
  }

  object "duration:Container" as duration {
    value=timedelta(hours=3)
  }

  object "prev:Container" as prev {
    value=None
  }

  object "desc:Container" as desc {
    value="write tutorial"
  }

  object "_rule_start:Rule" as _start {
    method=write._rule_start
  }

  object "_rule_end:Rule" as _end {
    method=write._rule_end
  }

  write o- "[0]" start
  end "[1]"--o write
  write o-- "[2]" duration
  prev "[3]"-o write
  desc "[4]"--o write
  write o-- "[0]" _start
  write o-- "[1]" _end

  _end --o start
  _end --o duration

  _start --o prev
  _start --o rend

  read o-- rend


Each :class:`~larch.reactive.Cell` attribute is a `descriptor
<https://docs.python.org/3/howto/descriptor.html>`_  that stores its
value in a `Container` object. `write` has an attribute
`__reactive_state__` containing a list of all Containers

For each rule method a `Rule` object is created and internally stored in the
`__reactive_rules__` attribute.

Each Container stores a list of its observers:

 - `_rule_end` observes `write.start` and `write.duration`.
 - `_rule_start` observes `write.prev` and `read.end`.


|bend| Object interaction
.........................

The following diagramms show the object interaction at line 31. (For more
in depth information read the code in pcore.py)

.. uml::

  autonumber

  participant "read.duration\n:Container" as rduration

  participant rcontext

  participant "read._rule_end\n:Rule" as _end

  participant "read.start\n:Container" as rstart

  participant "read.end\n:Container" as rend

  rduration -> rcontext : emit

  activate rcontext

  rcontext -> rcontext : start atomic action

  rcontext -> _end : ~__call__

  _end -> rstart : touch

  _end -> rduration: touch

  _end -> rend: set

  rend -> rcontext : emit

.. uml::

  autonumber 8

  participant rcontext

  participant "write._rule_start\n:Rule" as _start

  participant "write.prev\n:Container" as wprev

  participant "read.end\n:Container" as rend

  participant "write.start\n:Container" as wstart

  participant "write._rule_end\n:Rule" as _end

  activate rcontext

  rcontext -> _start : ~__call__

  _start -> wprev : touch

  _start -> rend : touch

  _start -> wstart : set

  wstart -> rcontext : emit

  rcontext -> _end : ~__call__
  note right of rcontext
  Same touch and set calls as in read._rule_end
  end note

  autonumber 17
  rcontext -> rcontext : atomic_end
  deactivate rcontext


`rcontext` is the short form of "reactive context". It is a global singleton
object managing the internal event system of |ra|.

1. When :class:`~larch.reactive.Cell` attribute (in this case `duration`) is
   changed the `Container` calls `emit` of rcontext.

2. `rcontext` enters an atomic stage.


Cell types
----------

While working with |ra| it turned out it is convenient to have some more
Cell objects.

:class:`~larch.reactive.TypeCell` is used to ensure the cell's value has
a specific type:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start TypeCell>
    :end-before: # <end TypeCell>
    :linenos:

:class:`~larch.reactive.MakeCell` constructs the default attribute by calling
a constructor:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start makecell>
    :end-before: # <end makecell>
    :linenos:

Keep in mind: For each new `ListContainer` object a new list is created.


Pointers
--------

A small observer class can be used to inspect cell attributes of an object.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start StartObserver>
    :end-before: # <end StartObserver>
    :linenos:

Remember that all rules will be called at construction, therefore the
start attribute is printed while the `StartObserver` is created.
The `StartObserver` class is not very flexible, it can only monitor start
attributes. Here is a better observer:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start ProxyObserver>
    :end-before: # <end ProxyObserver>
    :linenos:


A Pointer acts like a pointer in the C language. An expression like
`ra.Pointer(write).start` points to the attribute `start` of object `write`.
To get the value of a pointer you have to call it: `ra.Pointer(write).start()`.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start get-proxy-value>
    :end-before: # <end get-proxy-value>

You can also set an attribute value through a pointer:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start set-proxy-value>
    :end-before: # <end set-proxy-value>

Pointers can not only point to simple attributes but to whole expressions:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start proxy-expressions>
    :end-before: # <end proxy-expressions>


Last not least an improved  version of the :ref:`task example<firstuc>`.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start ProxyTask>
    :end-before: # <end ProxyTask>
    :linenos:

:class:`~larch.reactive.TypeCell` is used for `start` and `duration` to ensure
they contain pointers. The `prev` attribute is not needed anymore, the
dependencies are created by pointers.

.. note::

  The features of pointers:

  - Pointers will be evaluated when you call them.
  - Pointers can point to whole expressions.
  - The value of simple pointers can be set by calling the pointers with the
    new value.


Trivial Delegator
.................

The implementation of pointers offers a simple mechanism for a trivial delegator:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start trivial-delegator>
    :end-before: # <end trivial-delegator>
    :linenos:


Contexts
--------

Changing cell attributes can be influenced by contexts. Context's can also
be used as decorators.

:func:`~larch.reactive.atomic`
..............................

Changing cells within an atomic context, will postpone the call of rules after
the context finishes:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start atomic>
    :end-before: # <end atomic>
    :linenos:


Line 4-7:
  Every change will result in a immediate reactive reaction.

Line 9-13:
  Within an atomic context, the rules are called after the context ends.

.. note::

  Features of atomic contexts

  - rules are executed in an atomic context
  - in a gevent environment only one greenlet can execute an atomic context.

  If another greenlet wants to execute an atomic context it will be locked
  until the previous context has finished.


:func:`~larch.reactive.untouched`
.................................

Rules will connect to a all cells read by the rule. Sometimes you want
to avoid this:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start untouched>
    :end-before: # <end untouched>
    :linenos:

In line 14, the change of `duration` will trigger a change of `end`, but
`SillyTaskPrinter._rule_print` does not depend on `end`, therefore nothing
is printed.

.. warning::

  You should use this context only, if there is no other solution.
  It often signals bad practice.


:func:`~larch.reactive.silent`
.................................

If you want to change a cell without initiating the reactive reaction:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start silent>
    :end-before: # <end silent>
    :linenos:

Line 1:
  The `silent` context disables the reactive behaviour.

Line 4:
  `read` is in an inconsistent state: `start > end`.

Line 7:
  Calling the rule manually updates the depended attributes.

.. warning::

  You should use this context only, if there is no other solution.
  It often signals bad practice.

.. _yield_rules:

yield rules
-----------

Often rules should trigger a function with a big bunch of operations. Such a
function should be called outside the atomic context to ensure:

  - the rule should not depend on unwanted cells used in the function
  - in gevent environments the function should not lock other greenlets
    by locking the atomic context.

Therefore rules can be written as co-routines:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start yield-rule>
    :end-before: # <end yield-rule>
    :linenos:

The `yield` separates a rule into an atomic part above the `yield` and
an operational part after `yield`.


Rule Order
----------

At construction rules are called in the order of their appearance.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start rule_start>
    :end-before: # <end rule_start>
    :linenos:

As you can see `_rule_first` is called two times because "_rule_second" changes
`b` and `c` must be updated. An internal optimization mechanism, rearranges
the call order, to minimize the count of rule calls:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start rule_optimize>
    :end-before: # <end rule_optimize>
    :linenos:

|ra| can be forced to obey a call order by using the
:func:`~larch.reactive.rule` with a parameter.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start rule_order>
    :end-before: # <end rule_order>
    :linenos:


Agents
------

To inspect internals of a cell agents can be used.

:func:`~larch.reactive.old`
...........................

Within a rule :func:`~larch.reactive.old` delivers the value before the
cell was changed:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start old_agent>
    :end-before: # <end old_agent>
    :linenos:

Line 7:
  The `otask` object has the same cell attributes as `self.task` but
  their values are the values before the atomic context was entered.

Line 8:
  Only print if the values have changed.


.. note::

  **The Lifetime of Reactive objects**

  In line 17 the the printer is deactivated. This is because
  inside the reactive framework all references to objects are weakrefs. If
  an object is garbage collected all "cell to rule" connections will be also
  destroyed.


:func:`~larch.reactive.cell`
............................

The :func:`~larch.reactive.cell` agent delivers the internal
:class:`~larch.reactive.Container` object of the cell

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start cell_agent>
    :end-before: # <end cell_agent>
    :linenos:

The `cread` object has the same cell attributes as `self.task` but
their values point to the :class:`~larch.reactive.Container` objects,
containing their value.


Collections
-----------

|ra| provides subclasses of some standard mutable containers.

:func:`~larch.reactive.List`
............................

A list that fires events when it is changed. It provides two reactive
"event"-attributes: `__action_start__` is set before the list is changed,
and `__action_end__` is set after the list has changed.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start list>
    :end-before: # <end list>
    :linenos:

The example shows what you have to expect in the action attributes:
Their value is always None, if no event occurs. When the list is changed
first `__action_start__` is fired than `__action_end__` is fired.
The event is always a pair with the event type at the first place and
informations about the event in the second place.


:func:`~larch.reactive.Dict`
............................

Equally to List Dict is a reactive dictionary. It provides two reactive
"event"-attributes: `__action_start__` is set before the dictionary is
changed, and `__action_end__` is set after the list has changed.

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start dict>
    :end-before: # <end dict>
    :linenos:


Pickle
------

The reactive base class :func:`~larch.reactive.SimpleReactive` defines
the standard pickle methods `__getstate__` and `__setstate__` to pickle
the cells values by default.


Threading
---------

Reactive classes are not thread save but the state of an
:class:`ReactiveContext` is thread local.

This means: As long every :class:`Reactive` object is used by only one thread
you can work with several isolated threads. In Microsoft COM this is called
Apartment Threading Model.



|bend| Debugging Helpers
------------------------
Sometimes you got stuck, wondering why a rule is called. (Often because
the :ref:`best practice tips <bestpractice>` have been ignored). |ra| provides
some helper functions to find out what is going on:

.. literalinclude:: debug.txt
    :language: pycon
    :start-after: # <start debugging>
    :end-before: # <end debugging>
    :linenos:

The `dump` function of larch.reactive.debug inspects a reactive object
and prints for each cell the rules depending on that cell.

.. note::

  |ra| has a fast cython implementation that is imported by default, and
  a pure python implementation as fallback. The debugging helpers only work
  with the pure python implementation! Setting
  `os.environ["LARCH_REACTIVE"] = "python"` before(!) `import larch.reactive`
  will force to use the pure python version.


Within a `debug` context you atomic action are logged to a stream
(by default sys.stderr)

.. literalinclude:: debug.txt
    :language: pycon
    :start-after: # <start logging>
    :end-before: # <end logging>
    :linenos:

This is how you have to read the output:

Line 9:
  The "emit" commands says that some reactive rules will be called.
  In a real program you will see the source file name and line instead of
  `<console>(2): ''`.
  The embraced number is the atomic context recursion level: 1 is the outer
  most.

Line 10:
  After each emit command a list of rules to be called is printed.

Line 12:
  "call rule" is printed when a rule is executed, followed by some informations
  about the rule. After a call rule an indented block of actions inside the
  rule is printed.

Line 13-14:
  "touch" indicates the acces of a cell that binds the rule to the cell. (Here
  the cell `start` of the "read tutorial" task). The Line is followed by a
  traceback.

Line 19:
  Inside `_rule_end` `_rule_start` is emitted.
