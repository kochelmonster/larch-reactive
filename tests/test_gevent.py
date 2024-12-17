import unittest
import gevent
import gevent.event as gev
import larch.reactive as ra
import logconfig


class ShutDownExecution(BaseException):
    def __init__(self, calling):
        self.calling = calling


class Test(ra.Reactive):
    tick = ra.Cell(0)
    no_touch = ra.Cell(0)  # not touched by any rule
    set_event = ra.Cell(None)
    wait_for_kill = ra.Cell(0)
    second_rule = ra.Cell(0)
    throw_greenlet = ra.Cell(None)

    def __init__(self, set_event=None):
        self.set_event = set_event
        self.calls = []

    @ra.rule
    def update_tick(self):
        if self.tick:
            self.calls.append(("before", gevent.getcurrent()))
            gevent.sleep(0)
            self.calls.append(("after", gevent.getcurrent()))

    @ra.rule
    def _rule_set_event(self):
        if self.set_event:
            self.set_event.set()
            gevent.sleep(0)

    @ra.rule
    def _rule_wait_for_kill(self):
        if self.wait_for_kill:
            self.second_rule = 1
            gevent.sleep(1000)

    @ra.rule
    def _rule_second(self):
        if self.second_rule:
            self.calls.append("called second rule")

            def callback():
                self.calls.append("called callback")

            ra.call_outside(callback)

    @ra.rule
    def _rule_thow_exception(self):
        g = self.throw_greenlet
        if g is not None:
            g.throw(ShutDownExecution(gevent.getcurrent()))


class TestLock(ra.Reactive):
    lock1 = ra.Cell(0)
    lock2 = ra.Cell(0)
    lock3 = ra.Cell(0)

    @ra.rule
    def _rule_lock_src(self):
        self.lock1
        yield
        gevent.sleep(0)  # change to greenlet 2
        self.lock2 = self.lock1  # new atomic action may not lock

    @ra.rule
    def _rule_lock_cause(self):
        self.lock3
        gevent.sleep(0)  # change back to greenlet1 atomic count=1

    @ra.rule
    def _rule_lock2(self):
        self.lock2  # touch


class GeventTest(unittest.TestCase):
    def test_event(self):
        event = gev.Event()
        started = [False]

        def run():
            event.wait()
            started[0] = True

        greenlet = gevent.spawn(run)
        gevent.sleep(0)
        t = Test()
        t.set_event = event

        greenlet.join()
        self.assertTrue(started[0])

    def test_kill_rule(self):
        exit_called = []
        t = Test()

        def activate_wait_rule():
            try:
                t.wait_for_kill = 1
            except gevent.GreenletExit:
                exit_called.append(1)

        logconfig.logstream.truncate(0)
        g = gevent.spawn(activate_wait_rule)
        gevent.sleep(0)
        g.kill()
        g.join()
        self.assertTrue(g.ready())
        self.assertEqual(t.calls, ['called second rule', 'called callback'])
        self.assertEqual(exit_called, [1])
        self.assertIn("GreenletExit during observer notification",
                      logconfig.logstream.getvalue())

    def test_kill_callback(self):
        calls = []

        def prolog():
            calls.append("prolog")

        def sleep():
            calls.append("before sleep")
            gevent.sleep(100)
            calls.append("after sleep")

        def epilog():
            calls.append("epilog")

        def activate_callbacks():
            with ra.atomic():
                ra.call_outside(prolog)
                ra.call_outside(sleep)
                ra.call_outside(epilog)

        logconfig.logstream.truncate(0)
        g = gevent.spawn(activate_callbacks)
        gevent.sleep(0)
        g.kill()
        g.join()
        self.assertTrue(g.ready())
        self.assertEqual(calls, ['prolog', 'before sleep', 'epilog'])
        self.assertIn("GreenletExit while executing callback",
                      logconfig.logstream.getvalue())

    def test_rule_throw_exception(self):
        t1 = Test()
        t2 = Test()

        def do_throw(g):
            t2.throw_greenlet = g

        def tick():
            gevent.spawn(do_throw, gevent.getcurrent())
            try:
                t1.tick = 1
                self.assertFalse(True)
            except ShutDownExecution:
                self.assertFalse(False)

        gevent.spawn(tick)

    def test_lock(self):
        # this constellation caused an eternal jump in the gevent loop

        t = TestLock()

        def call_lock1():
            t.lock1 = 1

        def call_lock2():
            t.lock3 = 2

        g1 = gevent.spawn(call_lock1)
        g2 = gevent.spawn(call_lock2)

        gevent.joinall([g1, g2])


if __name__ == "__main__":
    unittest.main()
