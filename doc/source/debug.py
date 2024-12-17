from __future__ import unicode_literals
# <start debugging>
import os
os.environ["LARCH_REACTIVE"] = "python"
import sys
import larch.reactive as ra
import larch.reactive.debug as debug
from datetime import datetime, timedelta

@ra.reactive
class Task(object):
    start = ra.Cell(datetime.now())
    end = ra.Cell()
    duration = ra.Cell(timedelta(hours=3))
    prev = ra.Cell()
    desc = ra.Cell("")

    @ra.rule
    def _rule_start(self):
        if self.prev:
            self.start = self.prev.end

    @ra.rule
    def _rule_end(self):
        self.end = self.start + self.duration

    def __repr__(self):
        return "'{}'".format(self.desc)

read = Task(desc="read tutorial", start=datetime(2016, 1, 9, 8),
            duration=timedelta(hours=2))
write = Task(desc="write own programs", prev=read)

print(debug.dump(read))
# <end debugging>

sys.stderr = sys.stdout

# <start logging>
with debug.debug():
    read.start += timedelta(hours=0.5)

# <end logging>
