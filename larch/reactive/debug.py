from __future__ import print_function
import sys
import os.path
import linecache
from contextlib import contextmanager
from .core import rcontext, CellBase
from .base import cells_of, SimpleReactive
from pprint import pprint
if sys.version_info < (3, 0):
    from cStringIO import StringIO
else:
    from io import StringIO


@rcontext.untouched
def dump(obj, connected_only=True, line_ending="\n"):
    """
    dumps all cells and their dependent observers to a text string.
    """
    lines = []
    cells = cells_of(obj)

    lines.append("cells of %r" % obj)
    for cell in cells:
        container = cell.get_container(obj)
        observers = container.get_observers()
        if connected_only and not observers:
            continue

        lines.append("  %s(%s-%x)" % (cell.name, cell.__class__.__name__, id(container)))
        lines.extend(sorted("    %r(%x)" % (o, id(o)) for o in observers))

    return line_ending.join(lines)


class RContextPatcher(object):
    indent_count = 0

    def __init__(self, output=sys.stderr):
        self.output = output
        if type(rcontext).__module__ != "larch.reactive.pcore":
            raise RuntimeError("Only python module support debug context")

    def start(self, touch=True, emit=True, rule=True):
        self._org_rule_call = rcontext.rule_call
        self._org_touch = rcontext._touch
        self._org_emit = rcontext.emit

        if rule:
            rcontext.rule_call = self.rule_call
        if touch:
            rcontext._touch = self._touch
            if rcontext.touch == self._org_touch:
                rcontext.touch = self._touch

        if emit:
            rcontext.emit = self.emit

    def stop(self):
        if rcontext.rule_call == self.rule_call:
            del rcontext.rule_call
        if rcontext._touch == self._touch:
            del rcontext._touch
        if rcontext.emit == self.emit:
            del rcontext.emit

        if rcontext.touch == self._touch:
            rcontext.touch = rcontext._touch

    def indent(self):
        return "  " * (rcontext.atomic_count - 1 + self.indent_count)

    def write_indented(self, text, indent=None):
        indent = indent or self.indent()
        for i in text.splitlines():
            self.output.write(indent+i+"\n")

    def write(self, *args):
        s = StringIO()
        print(*args, file=s)
        self.write_indented(s.getvalue())

    def pprint(self, obj, indent=0):
        s = StringIO()
        pprint(obj, stream=s)
        indent = self.indent() + " " * indent
        self.write_indented(s.getvalue(), indent)

    def rule_call(self, rule, args, kwargs):
        self.write("call rule", repr(rule))
        self.indent_count += 1
        self._org_rule_call(rule, args, kwargs)
        self.indent_count -= 1
        self.write("")

    @rcontext.untouched
    def _touch(self, subject):
        try:
            cell, holder = self.find_cell(subject)
        except TypeError:
            holder = "unknown"
            cell = subject

        self._org_touch(subject)
        self.write("touch ({}.{})".format(holder, cell))
        for relevant, f in self.frames():
            if not relevant:
                continue

            line = self.get_source_line(f)
            line = "  {} in {}({}): {!r}".format(
                f.f_code.co_name, f.f_code.co_filename, f.f_lineno, line)
            self.write(line)

            try:
                # traceback until rule is reached
                cls = type(f.f_locals["self"])
                method = getattr(cls, f.f_code.co_name)
                if method.__rule__:
                    break
            except (KeyError, AttributeError):
                pass

        self.write("")
        return True

    def emit(self, observers):
        line = ""
        for relevant, f in self.frames():
            if relevant:
                line = self.get_source_line(f)
                line = "{}({}): {!r}".format(f.f_code.co_filename, f.f_lineno, line)
                break

        self.write("emit({}) {}".format(rcontext.atomic_count, line))
        with rcontext.untouched:
            self.pprint(observers, 2)
        self._org_emit(observers)
        self.write("")

    def find_cell(self, subject):
        for r, f in self.frames():
            holder = f.f_locals.get("holder")
            cell = f.f_locals.get("self")
            if not r and isinstance(holder, SimpleReactive) and isinstance(cell, CellBase):
                container = cell.get_container(holder)
                if container is subject:
                    return cell, holder

    def frames(self):
        # yields the frames outside reactive package
        f = sys._getframe()
        rpath = os.path.split(__file__)[0]
        while f:
            path = os.path.split(f.f_code.co_filename)[0]
            yield path != rpath, f
            f = f.f_back

    def get_source_line(self, frame):
        lineno = frame.f_lineno
        co = frame.f_code
        filename = co.co_filename
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, frame.f_globals)
        if line:
            return line.strip()
        return ""


@contextmanager
def debug(touch=True, emit=True, rule=True, output=sys.stderr):
    patcher = RContextPatcher(output)
    patcher.start(touch, emit, rule)
    try:
        yield
    finally:
        patcher.stop()
