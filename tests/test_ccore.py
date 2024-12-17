import unittest
from test_reactive import (RContextTest, PointerTest, AgentTest, CellTest,
                           TestReactive, MiscTest, ListTest, DictTest)
from test_thread import ThreadTest
from larch.reactive.core import core
try:
    import gevent
    from test_gevent import GeventTest
except ImportError:
    pass


class BackendTest(unittest.TestCase):
    def test_core(self):
        self.assertEqual(core, "c")


if __name__ == "__main__":
    unittest.main()
