"""
Tests threading and greenlet issues
"""
import threading
import larch.reactive as ra
import unittest


class Test(ra.Reactive):
    tick = ra.ResetCell(False)
    counter = 0

    @ra.rule
    def update_tick(self):
        if self.tick:
            self.counter += 1


class TestThread1(threading.Thread):
    def __init__(self):
        super(TestThread1, self).__init__()

    def run(self):
        self.test_obj = Test()

        for i in range(10):
            self.test_obj.tick = True

        self.rounds = ra.rcontext.rounds


class TestThread2(threading.Thread):
    def __init__(self):
        super(TestThread2, self).__init__()

    def run(self):
        self.test_obj = Test()

        for i in range(20):
            self.test_obj.tick = True

        self.rounds = ra.rcontext.rounds


class ThreadTest(unittest.TestCase):
    def test_threading(self):
        rounds = ra.rcontext.rounds
        t1 = TestThread1()
        t2 = TestThread2()

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertNotEqual(t1.rounds, t2.rounds)
        self.assertEqual(t1.test_obj.counter, 10)
        self.assertEqual(t2.test_obj.counter, 20)
        self.assertEqual(ra.rcontext.rounds, rounds)


if __name__ == "__main__":
    unittest.main()
