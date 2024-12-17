from __future__ import print_function
import sys
import larch.reactive as ra

import time
import cProfile



class RTest(ra.Reactive):
    cell1 = ra.Cell(10)
    cell2 = ra.Cell(11)

    """
    @ra.rule
    def check_cell1(self):
        assert(self.cell1 < 1000)
    """

rinstances = [ RTest() for i in range(1000) ]

def rread():
    for i in range(100):
        for t in rinstances:
            a = t.cell1
            b = t.cell2


def rwrite():
    for i in range(100):
        for t in rinstances:
            t.cell1 = i
            t.cell2 = i



class Test(object):
    def __init__(self):
        self.cell1 = 10
        self.cell2 = 11


instances = [ Test() for i in range(1000) ]

def read():
    for i in range(100):
        for t in instances:
            a = t.cell1
            b = t.cell2


def write():
    for i in range(100):
        for t in instances:
            t.cell1 = i
            t.cell2 = i


if 1:
    print("Original Objects")
    print("================")
    start = time.time()
    read()
    delta = (time.time() - start) * 1000
    print("read test", delta)


    start = time.time()
    write()
    delta = (time.time() - start) * 1000
    print("write test", delta)




print("Reactive Objects")
print("================")
if 1:
    start = time.time()
    rread()
    delta = (time.time() - start) * 1000
    print("read test", delta)

    start = time.time()
    rwrite()
    delta = (time.time() - start) * 1000
    print("write test", delta)


cProfile.run('rread()')
