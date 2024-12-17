"""
To use with coverage:
coverage erase
coverage run test_pcore.py
coverage combine
coverage report -m
"""
import os
os.environ["LARCH_REACTIVE"] = "python"
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
        self.assertEqual(core, "python")


if __name__ == "__main__":
    unittest.main(failfast=True)
