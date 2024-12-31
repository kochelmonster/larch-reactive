.. larch.reactive documentation master file, created by
   sphinx-quickstart on Fri Dec 17 13:52:51 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. |ra| replace:: `larch.reactive`

Welcome to |ra|'s documentation!
==========================================

|ra| is a `reactive programming library
<https://en.wikipedia.org/wiki/Reactive_programming>`_ for python.
The objectives of |ra| were:

  - to be lean
  - to be fast
  - compatible (it should be possible to add reactive behaviour
    to existing classes)
  - provide a consistent programming model.
  - debuggable

Lets start with an example to demonstrate how |ra| works:

.. literalinclude:: output.txt
    :language: pycon
    :start-after: # <start example1>
    :end-before: # <end example1>

A reactive class has cell attributes and rules that are called whenever a cell
has changed. For a more detailed discussion see :ref:`the first use
case.<firstuc>`


Installation
============

Install |ra|, either from a distribution package or from
`PyPI <https://pypi.python.org/pypi/larch.reactive>`_ with ::

   $ pip install larch-reactive


License
=======

|ra| is released under LGPL licence.


Contents
========

.. toctree::
   :maxdepth: 2

   examples
   reference


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
