import unittest
import larch.reactive as ra
import larch.reactive.rcollections as rc
from larch.reactive.pointer import _ExpressionOperandRoot
import pickle
# import larch.pickle as pickle
import gc
import weakref
import warnings
import logconfig
from contextlib import contextmanager
from operator import attrgetter


print("reactive.core", ra.core)


@contextmanager
def collect_warnings():
    messages = []

    def collect(message, category, filename, lineno, file=None, line=None):
        messages.append(message)

    old_warning = warnings.showwarning
    warnings.showwarning = collect
    try:
        yield messages
    finally:
        warnings.showwarning = old_warning


ra.add_pickle_extensions()


class RContextTester(ra.Reactive):
    a = ra.Cell(1)
    b = ra.Cell(2)
    c = ra.Cell(3)
    d = ra.Cell(4)
    calls = ra.MakeCell(list)

    @ra.rule(2)
    def _rule_b(self):
        if not ra.rcontext.inside_touch:
            raise RuntimeError("inside touch wrong")

        with ra.untouched():
            if ra.rcontext.inside_touch:
                raise RuntimeError("inside touch wrong")

            self.calls.append(("_rule_b in", self.a, self.b, self.c, self.d))

        self.c = self.b + 2
        self.d = self.b + 3

        with ra.untouched():
            self.calls.append(("_rule_b out", self.a, self.b, self.c, self.d))

    @ra.rule(3)
    def _rule_c(self):
        with ra.untouched():
            self.calls.append(("_rule_c in", self.a, self.b, self.c, self.d))

        self.d = self.c + 4

        with ra.untouched():
            self.calls.append(("_rule_c out", self.a, self.b, self.c, self.d))

    @ra.rule(4)
    def _rule_d(self):
        self.d
        with ra.untouched():
            self.calls.append(("_rule_d", self.a, self.b, self.c, self.d))

    @ra.rule(1)
    def _rule_a(self):
        with ra.untouched():
            self.calls.append(("_rule_a in", self.a, self.b, self.c, self.d))

        self.d = self.a + 3
        self.c = self.a + 2
        self.b = self.a + 1

        with ra.untouched():
            self.calls.append(("_rule_a out", self.a, self.b, self.c, self.d))


class RuleOrderTester(ra.Reactive):
    def __init__(self):
        self.called = []

    @ra.rule
    def _rule1(self):
        self.called.append("rule1")

    @ra.rule
    def _rule2(self):
        self.called.append("rule2")
        yield

    @ra.rule
    def _arule3(self):
        self.called.append("rule3")


class ErrorTester(ra.Reactive):
    callback_error = ra.Cell(0)
    recursive_error = ra.Cell(0)

    @ra.rule
    def _rule_callback_error(self):
        if self.callback_error:
            def outside():
                raise RuntimeError("callback_error")

            ra.rcontext.push_callback(outside)

    @ra.rule
    def _rule_recursive(self):
        if self.recursive_error:
            self.recursive_error += 1


class StopRuleTester(ra.Reactive):
    called = ra.Cell(0)
    iter_called = ra.Cell(0)

    @ra.rule
    def _rule_stop(self):
        if self.called == 1:
            # silently stop rule
            raise StopIteration()

    @ra.rule
    def _rule_iter_stop(self):
        called = self.iter_called
        yield
        if called == 1:
            # silently stop rule
            raise StopIteration()
        elif called == 2:
            raise RuntimeError()


class RContextTest(unittest.TestCase):
    def test_call_row(self):
        t = RContextTester()

        calls = [('_rule_a in', 1, 2, 3, 4),
                 ('_rule_a out', 1, 2, 3, 4),
                 ('_rule_b in', 1, 2, 3, 4),
                 ('_rule_b out', 1, 2, 4, 5),
                 ('_rule_c in', 1, 2, 4, 5),
                 ('_rule_c out', 1, 2, 4, 8),
                 ('_rule_d', 1, 2, 4, 8)]

        self.assertEqual(t.calls, calls)
        del t.calls[:]

        # tests also untouched
        t.a = 2
        calls = [('_rule_a in', 2, 2, 4, 8),
                 ('_rule_a out', 2, 3, 4, 5),
                 ('_rule_b in', 2, 3, 4, 5),
                 ('_rule_b out', 2, 3, 5, 6),
                 ('_rule_c in', 2, 3, 5, 6),
                 ('_rule_c out', 2, 3, 5, 9),
                 ('_rule_d', 2, 3, 5, 9)]

        self.assertEqual(t.calls, calls)
        del t.calls[:]

        t.b = 1
        calls = [('_rule_b in', 2, 1, 5, 9),
                 ('_rule_b out', 2, 1, 3, 4),
                 ('_rule_c in', 2, 1, 3, 4),
                 ('_rule_c out', 2, 1, 3, 7),
                 ('_rule_d', 2, 1, 3, 7)]

        self.assertEqual(t.calls, calls)
        del t.calls[:]

        t.c = 1
        calls = [('_rule_c in', 2, 1, 1, 7),
                 ('_rule_c out', 2, 1, 1, 5),
                 ('_rule_d', 2, 1, 1, 5)]

        self.assertEqual(t.calls, calls)

    def test_atomic(self):
        t = RContextTester()
        del t.calls[:]

        # from pudb import set_trace; set_trace()
        with ra.rcontext.atomic:
            t.a = 2
            t.d = 5

        calls = [('_rule_a in', 2, 2, 4, 5),
                 ('_rule_a out', 2, 3, 4, 5),
                 ('_rule_b in', 2, 3, 4, 5),
                 ('_rule_b out', 2, 3, 5, 6),
                 ('_rule_c in', 2, 3, 5, 6),
                 ('_rule_c out', 2, 3, 5, 9),
                 ('_rule_d', 2, 3, 5, 9)]

        self.assertEqual(t.a, 2)
        self.assertEqual(t.b, 3)
        self.assertEqual(t.c, 5)
        self.assertEqual(t.d, 9)

        self.assertEqual(t.calls, calls)
        del t.calls[:]

        with ra.rcontext.atomic:
            t.a = 1
            t.b = 8

        calls = [('_rule_a in', 1, 8, 5, 9),
                 ('_rule_a out', 1, 2, 3, 4),
                 ('_rule_b in', 1, 2, 3, 4),
                 ('_rule_b out', 1, 2, 4, 5),
                 ('_rule_c in', 1, 2, 4, 5),
                 ('_rule_c out', 1, 2, 4, 8),
                 ('_rule_d', 1, 2, 4, 8)]

        self.assertEqual(t.a, 1)
        self.assertEqual(t.b, 2)
        self.assertEqual(t.c, 4)
        self.assertEqual(t.d, 8)
        self.assertEqual(t.calls, calls)

    def test_silent(self):
        t = RContextTester()
        del t.calls[:]

        with ra.silent():
            t.a = 10

        self.assertEqual(t.calls, [])

    def test_misc(self):
        t = RContextTester()
        # should just not raise any exceptions
        ra.rcontext.rounds
        tc = ra.CellAgent(t)
        map(repr, tc.a.get_observers())
        self.assertIsInstance(tc.a, ra.Container)

    def test_callback_error(self):
        with collect_warnings() as messages:
            t = ErrorTester()
            t.callback_error = True

        self.assertEqual(len(messages), 1)
        self.assertIn("callback_error", repr(messages))

    def test_recursive_error(self):
        try:
            t = ErrorTester()
            t.recursive_error = 1
            self.assertFalse()
        except RuntimeError as e:
            self.assertIn("possible endless recursion", repr(e))


class RemoveWatcher(object):
    obj_removed = False

    def __init__(self, *args, **kwargs):
        super(RemoveWatcher, self).__init__(*args, **kwargs)
        self.__class__.obj_removed = False

    def __del__(self):
        self.__class__.obj_removed = True


@ra.reactive
class PointerChild(RemoveWatcher):
    a = ra.Cell(1)


@ra.reactive
class PointerChildChild(PointerChild):
    rule_called = False

    @ra.rule
    def _rule_is_reactive(self):
        self.rule_called = True


class PointerParent(RemoveWatcher, ra.Reactive):
    child = ra.Cell()
    children = ra.MakeCell(list)

    @ra.rule
    def _rule_set_children(self):
        self.children = [self.child]


class PointerTester:
    a = 1
    b = 2
    sum = ra.SELF.a + ra.SELF.b
    or_ = ra.SELF.a | ra.SELF.b
    and_ = ra.SELF.a & ra.SELF.b


class PointerObserver(RemoveWatcher, ra.Reactive):
    parent = ra.Cell()
    a = ra.SELF.parent.child.a
    old_a = 0

    @ra.rule
    def _rule_a(self):
        try:
            self.old_a = ra.OldAgent(self).a
        except ra.ResolveError:
            pass

        if ra.OldAgent(self).old_a != self.old_a:
            raise RuntimeError("not same")


def add(a, b):
    return 2 * a + b


class PointerTest(unittest.TestCase):
    def test_strong_ref(self):
        four = ra.Pointer(4)
        self.assertEqual(four(), 4)

    def test_delegator(self):
        c = PointerChild()
        p = PointerParent()
        o = PointerObserver()

        def wrong():
            o.a

        self.assertRaises(ra.ResolveError, wrong)

        o.parent = p
        self.assertRaises(ra.ResolveError, wrong)

        p.child = c
        self.assertEqual(o.a, 1)

        c.a = 10
        self.assertEqual(o.a, 10)
        self.assertEqual(o.old_a, 1)

        o.a = 20
        self.assertEqual(c.a, 20)
        self.assertEqual(o.old_a, 10)

        t = PointerTester()
        self.assertEqual(t.sum, 3)
        self.assertEqual(t.or_, 1)
        self.assertEqual(t.and_, 2)

    def test_same(self):
        o = PointerObserver(parent=PointerParent(child=PointerChild()))
        parent = o.parent

        pparent = ra.Pointer(parent)
        pchild = ra.Pointer(parent.child)

        p_pa = pparent.child.a
        p_pc = pparent.child

        self.assertEqual(p_pa, p_pa)
        self.assertEqual(p_pa, p_pc.a)
        self.assertEqual(p_pc.a, p_pa)
        self.assertEqual(p_pa, pchild.a)
        self.assertEqual(pchild.a, p_pa)
        self.assertNotEqual(p_pa, p_pc)
        self.assertNotEqual(p_pa, 2)

        p_pa1 = ra.Pointer(p_pa)
        self.assertEqual(p_pa1, p_pa)

    def test_single_pointer(self):
        c = PointerChild()
        pc = ra.Pointer(c)

        self.assertEqual(pc.a(), c.a)
        pc.a(2)
        self.assertEqual(c.a, 2)
        self.assertEqual(len(pc.a.__state__), 1)

        self.assertFalse(ra.Pointer())

    def test_pointer1(self):
        o = PointerObserver(parent=PointerParent(child=PointerChild()))

        pa = ra.Pointer(o).parent.child.a
        self.assertEqual(type(pa), ra.Pointer)
        self.assertEqual(str(pa), ".parent.child.a")
        self.assertEqual(hash(pa), hash(pa.__state__.path))

        o.a = 10
        self.assertEqual(o.parent.child.a, 10)
        self.assertEqual(pa(), 10)

    def test_pointer2(self):
        o = PointerObserver(parent=PointerParent(child=PointerChild()))

        pchild = ra.Pointer(o).parent.children[0]
        pa = ra.Pointer(o).parent.children[0].a

        pchild(None)
        self.assertEqual(bool(pa), False)
        self.assertEqual(o.parent.children, [None])

    def test_pointer_map(self):
        parent = PointerParent(child=PointerChild())
        pparent = ra.Pointer(parent)
        pmap = ra.PointerMap(child=pparent.child, a=pparent.child.a, parent=parent)

        self.assertEqual(pmap.get("child"), parent.child)
        self.assertEqual(pmap.get("a"), parent.child.a)
        self.assertEqual(pmap.get("parent"), parent)
        self.assertEqual(pmap.raw("child"), pparent.child)

        self.assertRaises(KeyError, pmap.get, "wrong")
        self.assertEqual(sorted(pmap.keys()), ['a', 'child', 'parent'])
        self.assertTrue("child" in pmap)

        pmap.set("a", 10)
        self.assertEqual(parent.child.a, 10)

        pmap.update(dict(a=20))
        self.assertEqual(pmap.get("a"), 20)

        self.assertTrue("a" in pmap)

        pmap.remove("child")
        self.assertRaises(KeyError, pmap.get, "child")

        pmap.set("value", 10)
        self.assertEqual(pmap.get("value"), 10)

    def test_compare_dumy_state(self):
        p1 = ra.Pointer()["name"].dir | "test"
        p2 = ra.Pointer()["name"].dir | "test"
        self.assertEqual(p1, p2)

    def get_proxies(self):
        self.t = PointerTester()
        return ra.Pointer(self.t).a, ra.Pointer(self.t).b

    def test_add(self):
        p1, p2 = self.get_proxies()
        p3 = p1 + p2
        self.assertEqual(p3(), 3)

        p1("ab")
        p2("cd")
        self.assertEqual(p3(), "abcd")

        p4 = p3[2]
        self.assertEqual(p4(), "c")

        p3 = "-" + p1
        self.assertEqual(p3(), "-ab")

    def test_sub(self):
        p1, p2 = self.get_proxies()
        p3 = p2 - p1
        self.assertEqual(p3(), 1)

        p3 = 10 - p2
        self.assertEqual(p3(), 8)

    def test_mul(self):
        p1, p2 = self.get_proxies()
        p3 = p2 * p1
        self.assertEqual(p3(), 2)

        p3 = 10 * p2
        self.assertEqual(p3(), 20)

    def test_div(self):
        p1, p2 = self.get_proxies()
        p1(4.0)
        p3 = p2 / p1
        self.assertEqual(p3(), 0.5)

        p3 = 10 / p2
        self.assertEqual(p3(), 5)

    def test_and(self):
        p1, p2 = self.get_proxies()
        p3 = p2 & p1
        self.assertEqual(p3(), 1)

        p3 = 10 & p2
        self.assertEqual(p3(), 2)

        pu = ra.Pointer().a
        p3 = p2 & pu
        self.assertFalse(p3())

        p3 = False & p2
        self.assertFalse(p3())

    def test_or(self):
        p1, p2 = self.get_proxies()
        p3 = p2 | p1
        self.assertEqual(p3(), 2)

        p3 = 10 | p2
        self.assertEqual(p3(), 10)

        p1(0)
        p3 = False | p1
        self.assertEqual(p3(), 0)

        pu = ra.Pointer().a
        p3 = False | pu | p1
        self.assertEqual(p3(), 0)

    def test_call(self):
        p1, p2 = self.get_proxies()
        p3 = ra.PointerExpression.call(add, p1, b=p2)
        self.assertEqual(p3(), 4)

    def test_compare(self):
        p1 = ra.Pointer().attr1
        p2 = ra.Pointer().attr2
        p3 = p1 & p2

        p4 = pickle.loads(pickle.dumps(p3))
        self.assertEqual(p3, p4)
        self.assertNotEqual(p3, p2)

        p4 = p1 | p2
        self.assertNotEqual(p3, p4)

    def test_apply(self):
        p1, p2 = self.get_proxies()
        p3 = ra.PointerExpression.apply(tuple, p1, p2)
        self.assertEqual(p3(), (1, 2))

    def test_set(self):
        p1, p2 = self.get_proxies()
        p3 = p2 + p1
        self.assertRaises(ValueError, p3, 3)

        p1(2)
        self.assertEqual(self.t.a, 2)

        p = ra.Pointer(self.t)
        self.assertRaises(TypeError, p, 2)

    def test_pickle(self):
        p1, p2 = self.get_proxies()

        x = pickle.dumps((self.t, p1))
        t, y = pickle.loads(x)
        self.assertEqual(y(), 1)

        p3 = p2 + p1
        x = pickle.dumps((self.t, p3))
        t, y = pickle.loads(x)
        self.assertEqual(y(), 3)

        p3 = p2 | p1
        x = pickle.dumps((self.t, p3))
        t, y = pickle.loads(x)
        self.assertEqual(y(), 2)

        p3 = ra.Pointer().a + ra.Pointer().b
        x = pickle.dumps(p3)
        y = pickle.loads(x)
        p4 = ra.merge_pointers(ra.Pointer(self.t), y)
        self.assertEqual(p4(), 3)

        p1, p2 = self.get_proxies()
        p3 = ra.PointerExpression.call(add, p1, b=p2)
        x = pickle.dumps((p3, self.t))
        y, t = pickle.loads(x)
        self.assertEqual(y(), 4)

        p1, p2 = self.get_proxies()
        p3 = ra.PointerExpression.call(add, p1, b=3)
        x = pickle.dumps(p3)
        y = pickle.loads(x)
        p4 = ra.merge_pointers(ra.Pointer(self.t), y)
        self.assertEqual(p4(), 5)
        self.assertEqual(y.__state__.delegate_get(self.t), 5)

    def test_backward_compatibility(self):
        ep = _ExpressionOperandRoot(add, [1, 2], {"a": 1})
        ep.__setstate__((add, [2, 3]))  # no exception
        self.assertEqual(ep.args, [2, 3])
        self.assertEqual(ep.kwargs, {})

    def test_equal_state(self):
        p = ra.Pointer()

        pin = p.a
        pout = pickle.loads(pickle.dumps(pin))
        self.assertEqual(pin.__state__, pout.__state__)

        pin = p.a + p.b
        pout = pickle.loads(pickle.dumps(pin))
        self.assertEqual(pin.__state__, pout.__state__)

        self.assertNotEqual((p.a + p.b).__state__, (p.a + p.c).__state__)
        self.assertNotEqual((p.a + p.b).__state__, (p.a - p.b).__state__)
        self.assertNotEqual((p.a | p.b).__state__, (p.a | p.c).__state__)
        self.assertNotEqual((p.a | p.b).__state__, (p.a + p.c).__state__)
        self.assertNotEqual(p.a.__state__, (p.a | p.c).__state__)

    def test_merge(self):
        # merge PointerState to PointerState
        p1 = ra.Pointer().a.b
        p2 = ra.Pointer().c.d
        p3 = ra.merge_pointers(p1, p2)
        self.assertEqual(str(p3), ".a.b.c.d")

        # merge PointerState to PointerExpression

        # _ExpressionOperandRoot.merge_to
        p1 = ra.Pointer().a
        p2 = ra.Pointer().b
        p3 = p1 + p2
        self.assertRaises(ra.ResolveError, p3)

        t = PointerTester()
        p4 = ra.merge_pointers(ra.Pointer(t), p3)
        self.assertEqual(p4(), 3)

        # _ExpressionRoot.merge_to
        p5 = p1 | p2
        self.assertFalse(p5())
        p6 = ra.merge_pointers(ra.Pointer(t), p5)
        self.assertEqual(p6(), 1)

        # merge PointerExpression to PointerState
        t.a = [1]
        t.b = [2]
        p5 = ra.merge_pointers(p4, ra.Pointer()[1])
        self.assertEqual(p5(), 2)

    def test_nothing(self):
        self.assertFalse(ra.NOTHING)

    def test_bool(self):
        p = PointerParent()
        pchild = ra.Pointer(p).child
        self.assertTrue(bool(pchild))

        pchild = ra.Pointer().child
        self.assertFalse(bool(pchild))

    def test_backward_load(self):
        data = [
            ("<Pointer-<class 'larch.reactive.pointer.NOTHING'>.test>",
             (b"\x80\x04\x95'\x00\x00\x00\x00\x00\x00\x00\x84\xc1\x8f"
              b"\x19-\x84\xf1\xab,R)\x81\x94\x84\xf7K\xb4p\x8c\x04test"
              b"\x94\x85\x94\x8c\x01a\x94\x87\x94b\x85\x94R\x94.")),
            ("<Pointer-and(<class 'larch.reactive.pointer.NOTHING'>.b,)>",
             (b'\x80\x04\x95>\x00\x00\x00\x00\x00\x00\x00\x84\xc1\x8f'
              b'\x19-\x84\xc3\xa0QH)\x81\x94\x84\xaf\x85\xd6})\x81\x94'
              b'\x84\xf1\xab,R)\x81\x94\x84\xf7K\xb4p\x8c\x01b\x94\x85'
              b'\x94\x8c\x01a\x94\x87\x94b\x85\x94b)\x8c\x00\x94\x87\x94b\x85\x94R\x94.')),
            ("<Pointer-or(<class 'larch.reactive.pointer.NOTHING'>.b,)>",
             (b'\x80\x04\x95>\x00\x00\x00\x00\x00\x00\x00\x84\xc1\x8f'
              b'\x19-\x84\xc3\xa0QH)\x81\x94\x84\xc9V-\x08)\x81\x94\x84'
              b'\xf1\xab,R)\x81\x94\x84\xf7K\xb4p\x8c\x01b\x94\x85\x94'
              b'\x8c\x01a\x94\x87\x94b\x85\x94b)\x8c\x00\x94\x87\x94b\x85\x94R\x94.')),
            (("<Pointer-add(<class 'larch.reactive.pointer.NOTHING'>.a, "
              "<class 'larch.reactive.pointer.NOTHING'>.b){}>"),
             (b'\x80\x04\x95p\x00\x00\x00\x00\x00\x00\x00\x84'
              b'\xc1\x8f\x19-\x84\xc3\xa0QH)\x81\x94\x84\x9c['
              b'\x91K)\x81\x94\x8c\rtest_reactive\x94\x8c\x03add'
              b'\x94\x93\x94\x84\xf1\xab,R)\x81\x94\x84\xf7K\xb4p'
              b'\x8c\x01a\x94\x85\x94h\x06\x87\x94b\x84\xf1\xab,R)'
              b'\x81\x94\x84\xf7K\xb4p\x8c\x01b\x94\x85\x94h\x06\x87'
              b'\x94b\x86\x94}\x94\x87\x94b)\x8c\x00\x94\x87\x94b\x85\x94R\x94.')),
            (("<Pointer-sum(<class 'larch.reactive.pointer.NOTHING'>.a, "
              "<class 'larch.reactive.pointer.NOTHING'>.b){}>"),
             (b'\x80\x04\x95k\x00\x00\x00\x00\x00\x00\x00\x84\xc1\x8f\x19-\x84\xc3\xa0QH)'
              b'\x81\x94\x84\x0e\xb4\xa4:)\x81\x94\x8c\x08builtins\x94\x8c\x03sum\x94\x93'
              b'\x94\x84\xf1\xab,R)\x81\x94\x84\xf7K\xb4p\x8c\x01a\x94\x85\x94h\x06\x87'
              b'\x94b\x84\xf1\xab,R)\x81\x94\x84\xf7K\xb4p\x8c\x01b\x94\x85\x94h\x06\x87'
              b'\x94b\x86\x94}\x94\x87\x94b)\x8c\x00\x94\x87\x94b\x85\x94R\x94.'))]

        for src, pkl in data:
            r = pickle.loads(pkl)
            self.assertEqual(repr(r), src)


class AgentTester(ra.Reactive):
    a = ra.Cell(1)
    old_a = 1
    old_ap = 1
    to_old_a = ra.SELF.old_a

    @ra.rule
    def _rule_a(self):
        self.old_a = ra.old(self).a
        self.old_ap = ra.old(self.a)


class AgentTest(unittest.TestCase):

    def test_old_agent(self):
        t = AgentTester()

        t.a = 10
        self.assertEqual(t.old_a, 1)

        t.a = 20
        self.assertEqual(t.old_a, 10)

        t2 = AgentTester(a=ra.Pointer(t).a)
        self.assertEqual(t2.old_ap, 20)

        t.a = 30
        self.assertEqual(t2.old_ap, 20)

        t.a = 40
        self.assertEqual(t2.old_ap, 30)

    def test_cell_agent(self):
        t1 = AgentTester()
        t2 = AgentTester()

        t1_cells = ra.CellAgent(t1)
        t2_cells = ra.CellAgent(t2)

        self.assertEqual(
            t1_cells.a.get_observers()[0].method,
            AgentTester._rule_a.__rule__[-1])
        self.assertEqual(t1_cells.a.get_observers()[0].holder(), t1)

        t1_cells.a = t2_cells.a

        t1.a = 10
        self.assertEqual(t2.a, 10)
        self.assertEqual(t1.old_a, 1)
        self.assertEqual(t2.old_a, 1)

        t2.a = 20
        self.assertEqual(t1.a, 20)
        self.assertEqual(t1.old_a, 10)
        self.assertEqual(t2.old_a, 10)

        def wrong():
            t1_cells.a = 1

        self.assertRaises(TypeError, wrong)

    def test_cell_agent_pointer(self):
        t1 = AgentTester()
        t2 = AgentTester()

        pa1 = ra.Pointer(t1).a
        pa2 = ra.Pointer(t2).a

        self.assertEqual(
            ra.cell(pa1).get_observers()[0].method,
            AgentTester._rule_a.__rule__[-1])
        self.assertEqual(ra.cell(pa1).get_observers()[0].holder(), t1)

        ra.cell(pa1, ra.cell(pa2))

        pa1(10)
        self.assertEqual(t2.a, 10)
        self.assertEqual(t1.old_a, 1)
        self.assertEqual(t2.old_a, 1)

        pa2(20)
        self.assertEqual(t1.a, 20)
        self.assertEqual(t1.old_a, 10)
        self.assertEqual(t2.old_a, 10)

        self.assertEqual(len(pa2), 0)
        self.assertRaises(TypeError, iter, pa2)

        del t1
        gc.collect()
        self.assertRaises(ra.ResolveError, pa1, 1)

    def test_errors(self):
        t = AgentTester()
        self.assertRaises(TypeError, ra.cell, ra.Pointer(t).a, 2)

        self.assertEqual(ra.old(ra.Pointer(t).old_a), 1)

        self.assertRaises(ra.ResolveError, ra.cell, ra.Pointer().a)

        def get_non_cell():
            ra.cell(t).to_old_a

        self.assertRaises(TypeError, get_non_cell)


class RobustString(str):

    def convert(self, other):
        return str(other)


class CellTester(ra.Reactive):
    a = ra.Cell()
    b = ra.TypeCell("")
    c = ra.ResetCell(False)
    d = ra.MakeCell(list, (1, 2, 3))
    e = ra.MakeTypeCell(list, (1, 2, 3))
    f = ra.TypeCell(RobustString(""))
    g = ra.TypeCell("", repr)

    @ra.rule
    def _rule_check_observer_callback(self):
        self.c


class NoString(object):

    def __str__(self):
        raise RuntimeError("no string")

    def __repr__(self):
        return "<NoString>"


class CellTest(unittest.TestCase):

    def test_cells(self):
        t = CellTester(a=1, b=2, c=True)

        self.assertEqual(t.a, 1)
        self.assertEqual(t.b, "2")
        self.assertEqual(t.c, False)
        self.assertEqual(t.d, [1, 2, 3])
        self.assertEqual(t.e, [1, 2, 3])

        t.d = (4, 5, 6)
        t.e = (4, 5, 6)

        self.assertEqual(t.d, (4, 5, 6))
        self.assertEqual(t.e, [4, 5, 6])

        t.c = True
        self.assertEqual(t.c, False)

        t.f = 10
        self.assertEqual(t.f, "10")

        try:
            t.b = NoString()
            self.assertFalse(True)
        except RuntimeError as e:
            self.assertEqual(e.args[1], CellTester.b)

        t.g = NoString()
        self.assertEqual(t.g, repr(NoString()))


class MultiBaseA(ra.Reactive):
    a = ra.Cell(1)
    b = ra.MakeCell(int, 2)
    calls = ra.MakeCell(list)

    @ra.rule(2)
    def _rule_a(self):
        with ra.rcontext.untouched:
            calls = self.calls

        calls.append(("a", self.a, self.b))


class MultiBaseB(ra.Reactive):
    b = ra.Cell(3)
    c = ra.Cell(4)
    d = ra.Cell(5)
    calls = ra.MakeCell(list)

    @ra.rule(3)
    def _rule_b(self):
        with ra.rcontext.untouched:
            calls = self.calls

        calls.append(("b", self.b, self.c, self.d))

    @ra.rule(4)
    def _rule_c(self):
        with ra.rcontext.untouched:
            calls = self.calls

        calls.append(("c", self.b))


class MulitSubC(MultiBaseA, MultiBaseB):
    a = ra.Cell(6)
    d = ra.Cell(7)
    e = ra.Cell(8)
    calls = ra.MakeCell(list)

    @ra.rule(1)
    def _rule_c(self):
        with ra.rcontext.untouched:
            calls = self.calls

        calls.append(("c", self.b, self.c))

    @ra.rule(5)
    def _rule_d(self):
        with ra.rcontext.untouched:
            calls = self.calls

        calls.append(("d", self.a, self.b, self.c, self.d, self.e))


class Observer(ra.Reactive):
    subject = ra.Cell()
    subjects_value = -1

    @ra.rule
    def _rule_set_value(self):
        if self.subject:
            self.subjects_value = self.subject.value


class Subject(ra.Reactive):
    value = ra.Cell(0)


class RuleOrder(ra.Reactive):
    def __init__(self):
        self.call_order = []

    @ra.rule
    def rule9(self):
        self.call_order.append(9)

    @ra.rule
    def rule5(self):
        self.call_order.append(5)

    @ra.rule
    def rule0(self):
        self.call_order.append(0)


class CircRef(ra.Reactive):
    value = ra.Cell()


class RuleBase(ra.Reactive):
    value = ra.Cell()

    def __init__(self):
        self.call_order = []

    @ra.rule
    def rule0(self):
        value = self.value
        yield
        self.call_order.append((0, value))


class RuleSuper(RuleBase):
    @ra.rule
    def rule0(self):
        # calling super generator rules
        g = super(RuleSuper, self).rule0()
        next(g)
        yield
        all(g)
        self.call_order.append((1, self.value))


class TestReactive(unittest.TestCase):

    def test_pickle(self):
        o1 = PointerObserver(parent=PointerParent(child=PointerChild()))

        o1.parent.child.a = 10
        self.assertEqual(o1.old_a, 1)

        o1.parent.child.a = 20
        self.assertEqual(o1.old_a, 10)

        # from pudb import set_trace; set_trace()
        picklestr = pickle.dumps(o1)

        o2 = pickle.loads(picklestr)
        self.assertEqual(o2.a, 20)
        self.assertEqual(o2.parent.child.a, 20)
        self.assertEqual(o2.old_a, 10)

    def test_multi(self):
        c = MulitSubC()

        self.assertEqual(c.a, 6)
        self.assertEqual(c.b, 2)
        self.assertEqual(c.c, 4)
        self.assertEqual(c.d, 7)
        self.assertEqual(c.e, 8)

        calls = [('c', 2, 4),
                 ('a', 6, 2),
                 ('b', 2, 4, 7),
                 ('d', 6, 2, 4, 7, 8)]

        self.assertEqual(c.calls, calls)
        # print ra.dump(c)

    def test_cells_of(self):
        self.assertEqual(list(map(attrgetter("name"), ra.cells_of(MulitSubC))),
                         ['b', 'c', 'a', 'd', 'e', 'calls'])

        self.assertEqual(
            list(map(attrgetter("name"), ra.cells_of(MulitSubC()))),
            ['b', 'c', 'a', 'd', 'e', 'calls'])

    def test_weak_refs(self):
        o = PointerObserver(parent=PointerParent(child=PointerChild()))
        self.assertEqual(PointerObserver.obj_removed, False)
        self.assertEqual(PointerParent.obj_removed, False)
        self.assertEqual(PointerChild.obj_removed, False)
        self.assertEqual(o.a, 1)

        o.parent.child = None
        gc.collect()
        self.assertEqual(PointerChild.obj_removed, True)
        observer = ra.cell(o).parent.get_observers()[0]

        del o
        gc.collect()
        self.assertEqual(PointerObserver.obj_removed, True)
        self.assertEqual(PointerParent.obj_removed, True)
        self.assertEqual(repr(observer)[:23], "<Rule obsolete _rule_a ")

    def test_decouple(self):
        # from pudb import set_trace; set_trace()
        subject1 = Subject()
        subject2 = Subject()
        observer = Observer(subject=subject1)

        self.assertEqual(observer.subjects_value, 0)

        subject1.value = 1
        self.assertEqual(observer.subjects_value, 1)

        subject2.value = 2
        self.assertEqual(observer.subjects_value, 1)

        observer.subject = subject2
        self.assertEqual(observer.subjects_value, 2)

        subject1.value = 10
        self.assertEqual(observer.subjects_value, 2)

        subject2.value = 3
        self.assertEqual(observer.subjects_value, 3)

    def test_rule_order(self):
        ro = RuleOrder()
        self.assertEqual(ro.call_order, [9, 5, 0])

    def test_subclass(self):
        ccp = PointerChildChild()
        self.assertEqual(ccp.rule_called, True)

    def test_circula_ref(self):
        gc.disable()

        a = CircRef()
        b = CircRef()
        # circular reference
        a.value = b
        b.value = a

        c = weakref.ref(a)
        del a
        del b
        # not garage collected (circular refcount)
        self.assertTrue(bool(c()))
        gc.collect()
        gc.enable()
        self.assertFalse(bool(c()))

    def test_rule_super(self):
        ro = RuleSuper()
        self.assertEqual(ro.call_order, [(0, None), (1, None)])
        ro.call_order = []
        ro.value = 5
        self.assertEqual(ro.call_order, [(0, 5), (1, 5)])

    def test_stop_rule(self):
        r = StopRuleTester()

        with collect_warnings() as messages:
            r.iter_called = 1
        self.assertFalse(messages)

        with collect_warnings() as messages:
            r.called = 1
        self.assertFalse(messages)

        # nothing happens
        logconfig.logstream.truncate(0)
        with collect_warnings() as messages:
            r.iter_called = 2
        self.assertIn("RuntimeError", str(messages[0]))


class MiscTester(ra.Reactive):
    a = ra.ResetCell(False)
    b = ra.ResetCell(False)
    will_raise = ra.ResetCell(False)
    will_raise_outside = ra.ResetCell(False)
    c = ra.ResetCell(False)
    d = ra.ResetCell(False)
    double_count = 0

    e = ra.ResetCell(False)
    f = ra.ResetCell(False)
    g = ra.ResetCell(False)
    reinsert_count = 0

    @ra.rule
    @ra.untouched()
    def _rule_b(self):
        if not ra.rcontext.inside_rule:
            raise RuntimeError("inside rule wrong")

        with ra.touched():
            self.b

    @ra.rule
    def _rule_will_raise(self):
        if self.will_raise:
            raise RuntimeError("raise exception")

    @ra.rule
    def _rule_double(self):
        self.c
        self.d
        self.double_count += 1

    @ra.rule
    def _rule_reinsert(self):
        self.reinsert_count += 1
        if self.e and not self.f:
            self.f = True

    @ra.rule
    def _rule_raise_outside(self):
        def raise_outside():
            raise RuntimeError("")

        if self.will_raise_outside:
            ra.call_outside(raise_outside)

    @ra.rule
    def _rule_coroutine(self):
        if self.g:
            self.co_call = [(0, ra.rcontext.transaction_level)]
            yield
            self.co_call.append((1, ra.rcontext.transaction_level))
            yield
            self.co_call.append((2, ra.rcontext.transaction_level))


class Control(ra.Reactive):
    view = ra.Cell()

    def __init__(self, view):
        self.view = view
        self.calls = []

    @ra.rule
    def _rule_value_changed(self):
        self.calls.append(self.view.value)


class View(ra.Reactive):
    """A situation that failed in practice"""
    value = ra.Cell()
    old_value = None

    @ra.rule(1)
    def _rule_create_control(self):
        if self.old_value is None:
            self.control = Control(self)

        self.old_value = self.value


class DirectRuleCall(ra.Reactive):
    a = ra.Cell(1)
    called = None

    @ra.rule
    def _rule_activation(self, activate=None):
        if activate is None:
            self.called = self.a

        elif activate is False:
            self.called = None

        else:
            self.a
            self.called = None


class MissingObserverTest(ra.Reactive):
    cell1 = ra.Cell(False)
    cell2 = ra.Cell(0)

    @ra.atomic()
    def start_test(self):
        self.cell2 = 1
        self.cell1 = True

    @ra.rule
    def _rule_for_cell2(self):
        self.value2 = self.cell2  # touch

    @ra.rule
    def _rule_missing(self):
        if self.cell1:
            self.value = self.cell2

    @ra.rule
    def _rule_fire_cell2(self):
        if self.cell1:
            self.cell2 = 2


class MiscTest(unittest.TestCase):
    """to complete code coverage"""

    def test_callback_stack(self):
        called_ids = []

        def call_inner():
            called_ids.append("inner")

        def call_outer():
            with ra.atomic():
                called_ids.append("inner")
            self.assertEqual(called_ids, ["inner"])
            called_ids.append("outer")

        with ra.atomic():
            ra.call_outside(call_outer)
            ra.call_outside(call_inner)

        self.assertEqual(called_ids, ["inner", "outer", "inner"])

    def test_missing_observer(self):
        # tests a bug
        m = MissingObserverTest()
        m.start_test()
        self.assertEqual(m.value, 2)

    def test_doubled_rule(self):
        t = MiscTester()

        # without transaction
        t.double_count = 0
        t.c = 1
        t.d = 2
        self.assertEqual(t.double_count, 2)

        def check_after():
            self.assertEqual(t.double_count, 1)
            t.check_called = True

        with ra.atomic():
            self.assertFalse(ra.rcontext.inside_rule)
            t.c = 1
            t.c = 1
            t.d = 2

            observers = ra.rcontext.observers
            self.assertEqual(len(observers), 2)
            self.assertEqual(observers[0], observers[1])
            t.double_count = 0
            ra.call_outside(check_after)

        self.assertEqual(t.double_count, 1)
        self.assertEqual(t.check_called, True)

        t.check_called = False
        ra.call_outside(check_after)
        self.assertEqual(t.check_called, True)

    def test_reinsert_rule(self):
        t = MiscTester()
        t.reinsert_count = 0
        t.e = True
        self.assertEqual(t.reinsert_count, 2)

    def test_empty_call_back(self):
        t = MiscTester()
        with ra.rcontext.atomic:
            t.a = True

        self.assertEqual(t.a, False)

    def test_dumy_call_back(self):
        t = MiscTester()
        with ra.rcontext.silent:
            t.b = True

        self.assertEqual(t.b, False)

    def test_rule_exception(self):
        t = MiscTester()

        logconfig.logstream.truncate(0)
        with collect_warnings() as messages:
            t.will_raise = True

        self.assertEqual(len(messages), 1)
        self.assertIn("_rule_will_raise", str(messages[0]))
        self.assertIn("RuntimeError: raise exception",
                      logconfig.logstream.getvalue())

    def test_outside_exception(self):
        t = MiscTester()

        with collect_warnings() as messages:
            t.will_raise_outside = True

        self.assertEqual(len(messages), 1)
        self.assertIn("raise_outside", str(messages[0]))

    def test_coroutine_rule(self):
        t = MiscTester()
        t.g = True
        self.assertEqual(t.co_call, [(0, 1), (1, 0), (2, 0)])

    def test_counter_error(self):
        # the Control _rule_value_changed was detached because
        # _rule_create_control has a smaller counter than _rule_value_changed
        view = View()
        view.value = 1
        self.assertEqual(view.control.calls, [1])
        view.value = 2
        self.assertEqual(view.control.calls, [1, 2])

    def test_init_rule_order(self):
        t = RuleOrderTester()
        self.assertEqual(t.called, ['rule1', 'rule2', 'rule3'])

    def test_direct_rule_call(self):
        o = DirectRuleCall()

        # rule is activated by default
        self.assertEqual(o.called, 1)

        o.a = 2
        self.assertEqual(o.called, 2)

        # rule is deactivated
        # from pudb import set_trace; set_trace()
        o._rule_activation(False)
        self.assertEqual(o.called, None)

        o.a = 3
        self.assertEqual(o.called, None)

        # rule reactivated
        o._rule_activation(True)
        self.assertEqual(o.called, None)

        o.a = 4
        self.assertEqual(o.called, 4)

    def test_agent_dir(self):
        t = RContextTester()
        tc = ra.CellAgent(t)
        self.assertEqual(dir(tc), ['a', 'b', 'c', 'calls', 'd'])


class ListTester(ra.Reactive):
    li = ra.MakeCell(rc.List)
    add = ra.ResetCell(None)

    def __init__(self):
        self.calls = []

    @ra.rule
    def _rule_add(self):
        if self.add is not None:
            self.li.append(self.add)

    @ra.rule
    def _rule_start(self):
        if self.li.__action_start__:
            self.calls.append(("start", self.li.__action_start__))

    @ra.rule
    def _rule_end(self):
        if self.li.__action_end__:
            self.calls.append(("end", self.li.__action_end__))


class ListTest(unittest.TestCase):
    def test_sandwich(self):
        lt = ListTester()
        lt.add = 1
        self.assertEqual(lt.calls, [('start', ('insert', (0, 1))),
                                    ('end', ('insert', (0, 1)))])
        self.assertEqual(lt.li, [1])

    def test_manipulation(self):
        lt = ListTester()
        lt.li[:] = [1, 2, 3, 4]

        calls = [('start', ('change', (slice(0, 0, None), [1, 2, 3, 4]))),
                 ('end', ('change', (slice(0, 0, None), [1, 2, 3, 4])))]

        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('change', (slice(2, 4, None), [5, 6, 7]))),
                 ('end', ('change', (slice(2, 4, None), [5, 6, 7])))]
        lt.li[-2:] = [5, 6, 7]
        self.assertEqual(lt.li, [1, 2, 5, 6, 7])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('delete', slice(3, 4, None))),
                 ('end', ('delete', slice(3, 4, None)))]

        del lt.li[-2]
        self.assertEqual(lt.li, [1, 2, 5, 7])
        self.assertEqual(lt.calls, calls)

        del lt.li[len(lt.li):]  # nothing changed
        self.assertEqual(lt.li, [1, 2, 5, 7])
        self.assertEqual(lt.calls, calls)

        lt.li[1:1] = []  # nothing changed
        self.assertEqual(lt.li, [1, 2, 5, 7])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('delete', slice(1, 2, None))),
                 ('end', ('delete', slice(1, 2, None)))]

        lt.li.remove(2)
        self.assertEqual(lt.li, [1, 5, 7])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('delete', slice(2, 3, None))),
                 ('end', ('delete', slice(2, 3, None)))]

        lt.li.pop(-1)
        self.assertEqual(lt.li, [1, 5])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('change', (slice(1, 2, None), [6]))),
                 ('end', ('change', (slice(1, 2, None), [6])))]

        lt.li[-1] = 6
        self.assertEqual(lt.li, [1, 6])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('delete', slice(0, 2, None))),
                 ('end', ('delete', slice(0, 2, None)))]

        lt.li[:] = []
        self.assertEqual(lt.li, [])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('insert', (0, 1))), ('end', ('insert', (0, 1)))]
        lt.li.insert(0, 1)
        self.assertEqual(lt.li, [1])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('extend', [2, 3])), ('end', ('extend', [2, 3]))]
        lt.li.extend([2, 3])
        self.assertEqual(lt.li, [1, 2, 3])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('extend', [4, 5])), ('end', ('extend', [4, 5]))]
        lt.li += [4, 5]
        self.assertEqual(lt.li, [1, 2, 3, 4, 5])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('imul', 2)), ('end', ('imul', 2))]
        lt.li *= 2
        self.assertEqual(lt.li, [1, 2, 3, 4, 5] * 2)
        self.assertEqual(lt.calls, calls)

        lt.li[:] = [1, 2, 3]
        lt.calls = []
        calls = [('start', ('order', 'reverse')),
                 ('end', ('order', 'reverse'))]
        lt.li.reverse()
        self.assertEqual(lt.li, [3, 2, 1])
        self.assertEqual(lt.calls, calls)

        lt.calls = []
        calls = [('start', ('order', 'sort')), ('end', ('order', 'sort'))]
        lt.li.sort()
        self.assertEqual(lt.li, [1, 2, 3])
        self.assertEqual(lt.calls, calls)

    def test_pickle(self):
        lt = ListTester()
        lt.li[:] = [1, 2, 3, 4]

        x = pickle.dumps(lt.li, -1)
        y = pickle.loads(x)

        self.assertEqual(y, lt.li)
        self.assertEqual(type(y), type(lt.li))


class DictTester(ra.Reactive):
    d = ra.MakeCell(rc.Dict)
    change = ra.ResetCell(None)

    def __init__(self):
        self.calls = []

    @ra.rule
    def _rule_change(self):
        if self.change is None:
            return

        action, key, value = self.change
        if action == "set":
            self.d[key] = value
        else:
            del self.d[key]

    @ra.rule
    def _rule_start(self):
        if self.d.__action_start__:
            self.calls.append(("start", self.d.__action_start__))

    @ra.rule
    def _rule_end(self):
        if self.d.__action_end__:
            self.calls.append(("end", self.d.__action_end__))


class DictTest(unittest.TestCase):

    def test_sandwich(self):
        dt = DictTester()
        # from pudb import set_trace; set_trace()
        dt.change = ("set", "test", 1)
        self.assertEqual(dt.calls, [('start', ('change', ('test', 1))),
                                    ('end', ('change', ('test', 1)))])
        self.assertEqual(dt.d, {'test': 1})

    def test_manipulation(self):
        dt = DictTester()
        dt.d[1] = 2

        calls = [('start', ('change', (1, 2))),
                 ('end', ('change', (1, 2)))]

        self.assertEqual(dt.calls, calls)

        # delete
        dt.calls = []
        del dt.d[1]
        calls = [('start', ('delete', 1)), ('end', ('delete', 1))]
        self.assertEqual(dt.calls, calls)

        # update
        dt.calls = []
        dt.d.update({1: 2, 2: 3, 3: 4})

        calls = [('start', ('update', (({1: 2, 2: 3, 3: 4},), {}))),
                 ('end', ('update', (({1: 2, 2: 3, 3: 4},), {})))]
        self.assertEqual(dt.calls, calls)

        # pop
        dt.calls = []
        r = dt.d.pop(1)
        calls = [('start', ('delete', 1)),
                 ('end', ('delete', 1))]
        self.assertEqual(r, 2)
        self.assertEqual(dt.calls, calls)

        dt.calls = []
        r = dt.d.pop(None, 1)
        self.assertEqual(r, 1)
        self.assertEqual(dt.calls, [])

        dt.calls = []
        self.assertRaises(KeyError, dt.d.pop, None)
        self.assertEqual(dt.calls, [])

        # delete unknown key
        dt.calls = []
        self.assertRaises(KeyError, dt.d.__delitem__, None)
        self.assertEqual(dt.calls, [])  # nothing changed

        # setdefault
        dt.calls = []
        calls = [('start', ('change', ('default', 1))),
                 ('end', ('change', ('default', 1)))]

        dt.d.setdefault("default", 1)
        self.assertEqual(dt.calls, calls)

        # popitem
        dt.calls = []
        item = dt.d.popitem()
        calls = [('start', ('delete', item[0])), ('end', ('delete', item[0]))]
        self.assertEqual(dt.calls, calls)

        # clear
        dt.calls = []
        calls = [('start', ('clear', None)), ('end', ('clear', None))]
        dt.d.clear()
        self.assertEqual(dt.calls, calls)
        self.assertRaises(KeyError, dt.d.popitem)

    def test_pickle(self):
        dt = DictTester()
        dt.d.update({1: 2, 2: 3, 3: 4})

        ds = pickle.dumps(dt.d, -1)
        d = pickle.loads(ds)

        self.assertEqual(d, dt.d)
        self.assertEqual(type(d), type(dt.d))


class TempConverter(ra.Reactive):
    F = ra.Cell(32)
    C = ra.Cell(0)

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @ra.rule
    def convert_fahrenheit(self):
        self.F = self.C * 1.8 + 32

    @ra.rule
    def convert_celsius(self):
        self.C = (self.F - 32) / 1.8


class DocTest(unittest.TestCase):
    def test_temp(self):
        # from pudb import set_trace; set_trace()
        tc = TempConverter(C=100)
        self.assertEqual(tc.C, 100)
        self.assertEqual(tc.F, 212)

        tc.F = 32.0
        self.assertEqual(tc.C, 0)
        self.assertEqual(tc.F, 32)

        tc.C = -40.0
        self.assertEqual(tc.C, -40)
        self.assertEqual(tc.F, -40)


if __name__ == "__main__":
    unittest.main()
