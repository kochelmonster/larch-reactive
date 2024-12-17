from __future__ import print_function

# <start example1>
import larch.reactive as ra
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
        return "'{}': {} -> {}".format(self.desc, self.start, self.end)

read = Task(desc="read tutorial", start=datetime(2016, 1, 9, 8),
            duration=timedelta(hours=2))
read
write = Task(desc="write own programs", prev=read)
write
read.duration = timedelta(hours=3)
read
write
# <end example1>


# <start TypeCell>
@ra.reactive
class Point(object):
    x = ra.TypeCell(0)
    y = ra.TypeCell(0, converter=float)

p = Point(x="1", y="2")
p.x
p.y
# <end TypeCell>


# <start makecell>
@ra.reactive
class ListContainer(object):
    values = ra.MakeCell(list, (1, 2, 3))

lc = ListContainer()
lc.values
# <end makecell>


# <start StartObserver>
@ra.reactive
class StartObserver(object):
    subject = ra.Cell()

    @ra.rule
    def _rule_print(self):
        print("start:", self.subject.start)

observer = StartObserver(subject=write)
read.start += timedelta(hours=0.5)
del observer  # deactivate observer
# <end StartObserver>


# <start ProxyObserver>
@ra.reactive
class PointerObserver(object):
    subject = ra.Cell()

    @ra.rule
    def _rule_print(self):
        print("attribute:", repr(self.subject), self.subject())

observer = PointerObserver(subject=ra.Pointer(write).start)
read.start += timedelta(hours=0.5)
# <end ProxyObserver>

# <start get-proxy-value>
ra.Pointer(write).start() == write.start
# <end get-proxy-value>

# <start set-proxy-value>
ra.Pointer(read).start(datetime(2016, 2, 9, 11))
# <end set-proxy-value>

# <start proxy-expressions>
# prints write.start + 30min
observer = PointerObserver(subject=ra.Pointer(write).start + timedelta(minutes=30))

# prints the maximum of read.end and write.end
observer = PointerObserver(subject=ra.PointerExpression.call(
    max, ra.Pointer(read).end, ra.Pointer(write).end))
del observer  # deactivate observer
# <end proxy-expressions>


# <start ProxyTask>
@ra.reactive
class PointerTask(object):
    start = ra.TypeCell(ra.Pointer(datetime.now()), converter=ra.Pointer)
    end = ra.Cell()
    duration = ra.TypeCell(ra.Pointer(timedelta(hours=3)), converter=ra.Pointer)
    desc = ra.Cell("")

    @ra.rule
    def _rule_end(self):
        self.end = self.start() + self.duration()

    def __repr__(self):
        return "'{}': {} -> {}".format(self.desc, self.start(), self.end)

pread = PointerTask(desc="read tutorial", start=datetime(2016, 1, 9, 8),
                  duration=timedelta(hours=2))
pwrite = PointerTask(desc="write own programs", start=ra.Pointer(pread).end)
pread
pwrite
# <end ProxyTask>


# <start trivial-delegator>
@ra.reactive
class TaskPrinter(object):
    task = ra.Cell()
    # make task attributes to my own
    start = ra.SELF.task.start
    end = ra.SELF.task.end
    desc = ra.SELF.task.desc

    @ra.rule
    def _rule_print(self):
        print("'{}': {} -> {}".format(self.desc, self.start, self.end))

printer = TaskPrinter(task=write)
del printer  # deactivate printer
# <end trivial-delegator>


# <start atomic>
printer = TaskPrinter(task=read)

read.start = datetime(2016, 1, 8, 8)
read.duration = timedelta(hours=2)

with ra.atomic():
    read.start = datetime(2016, 1, 9, 8)
    read.duration = timedelta(hours=3)

del printer  # deactivate printer
# <end atomic>


# <start untouched>
@ra.reactive
class SillyTaskPrinter(object):
    task = ra.Cell()

    @ra.rule
    def _rule_print(self):
        # this rule does not depend on self.task.end
        with ra.untouched():
            end = self.task.end
        print("'{}': {} -> {}".format(self.task.desc, self.task.start, end))

printer = SillyTaskPrinter(task=read)
read.duration = timedelta(hours=2.5)
read.start = datetime(2016, 1, 8, 8)

del printer  # deactivate printer
# <end untouched>

# <start silent>
with ra.silent():
    read.start = datetime(2016, 1, 9, 8)

read

read._rule_end()
read
# <end silent>


# <start yield-rule>
@ra.reactive
class TaskObserver(object):
    task = ra.Cell()

    @ra.rule
    def _rule_trigger_action(self):
        self.task.end  # touch without using the value
        yield
        # many operations using different cells
        # the rule does not depend on these cells
# <end yield-rule>


# <start rule_start>
@ra.reactive
class RuleOrderDemo(object):
    a = ra.Cell(0)
    b = ra.Cell(0)
    c = ra.Cell(0)

    @ra.rule
    def _rule_first(self):
        self.c = self.b + 1
        print("rule first is called c =", self.c)

    @ra.rule
    def _rule_second(self):
        self.b = self.a + 1
        print("rule second is called b =", self.b)

demo = RuleOrderDemo()
demo.a, demo.b, demo.c
# <end rule_start>

# <start rule_optimize>
demo.a = 2
# <end rule_optimize>

# <start rule_order>
@ra.reactive
class RuleOrderDemo(object):
    a = ra.Cell(0)
    b = ra.Cell(0)
    c = ra.Cell(0)

    @ra.rule(2)
    def _rule_first(self):
        self.c = self.b + 1
        print("rule first is called c =", self.c)

    @ra.rule(1)
    def _rule_second(self):
        self.b = self.a + 1
        print("rule second is called b =", self.b)

demo = RuleOrderDemo()
# <end rule_order>


# <start old_agent>
@ra.reactive
class TaskPrinter(object):
    task = ra.Cell()

    @ra.rule
    def _rule_print(self):
        otask = ra.old(self.task)
        if otask.start == self.task.start and otask.end == self.task.end:
            return
        print("'{}': {}({}) -> {}({})".format(
            self.task.desc, self.task.start, otask.start,
            self.task.end, otask.end))

printer = TaskPrinter(task=read)
read.start = datetime(2016, 1, 8, 8)
del printer  # deactivate printer
# <end old_agent>


# <start cell_agent>
cread = ra.cell(read)
cread.end
cread.end.get_observers()
cread.end.get_value()
# <end cell_agent>

# <start list>
@ra.reactive
class ContainerObserver(object):
    subject = ra.Cell()

    @ra.rule
    def _rule_print_start(self):
        print("action start:", self.subject.__action_start__)

    @ra.rule
    def _rule_print_end(self):
        print("action end:", self.subject.__action_end__)

from larch.reactive.rcollections import List
container = List()
observer = ContainerObserver(subject=container)

container.append(1)

container[0] = 2

container[:] = [1, 2, 3]

container.reverse()

container.sort()

container += [4, 5, 6]

container *= 2

del container[2:-2]
# <end list>

# <start dict>
from larch.reactive.rcollections import Dict
container = Dict()
observer = ContainerObserver(subject=container)

container[1] = "one"

container.update({2: "two", 3: "three"})

container.popitem()

container.clear()
# <end dict>
