Library Reference
=================

`larch.reactive`
----------------

.. module:: larch.reactive

.. autofunction:: atomic

.. autofunction:: untouched

.. autofunction:: touched

.. autofunction:: silent

.. autofunction:: reactive

.. autofunction:: rule

.. autofunction:: reactive

.. autofunction:: cells_of

.. autofunction:: old

.. autofunction:: cell

.. autofunction:: call_outside

.. autoclass:: Cell

.. autoclass:: TypeCell

.. autoclass:: MakeCell

.. autoclass:: MakeTypeCell

.. autoclass:: SimpleReactive

.. autoclass:: Pointer

.. autoclass:: PointerExpression
    :members: call, apply

.. autofunction:: merge_pointers


.. module:: larch.reactive.pcore

.. autoclass:: ReactiveContext
    :members: rounds, transaction_level, inside_rule, inside_touch

.. autoclass:: Container
    :members: get_value, set_value, get_observers


`larch.reactive.rcollections`
-----------------------------

.. module:: larch.reactive.rcollections
