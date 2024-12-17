from __future__ import print_function
import os
os.environ["LARCH_REACTIVE"] = "python"
import larch.reactive as ra
import larch.reactive.debug as dbg


class Test(ra.Reactive):
    a = ra.Cell()
    b = ra.Cell()
    error = ra.Cell()

    def print_a(self):
        print("a=", repr(self.a))

    @ra.rule
    def _rule_a(self):
        if self.a:
            self.print_a()

    @ra.rule
    def _rule_b(self):
        if self.b:
            with dbg.debug():
                print(self.b)
                self.a = 2

    @ra.rule
    def _rule_error(self):
        if self.error:
            raise RuntimeError()

t = Test()

print("debug rule a")
with dbg.debug():
    t.a = 1

print("------------------")
print("call rule b")
t.b = 1

print("------------------")
print("error")
t.error = 1
