from __future__ import print_function
import code
import fileinput


def indentation(s, tabsize=4):
    sx = s.expandtabs(tabsize)
    return 0 if sx.isspace() else len(sx) - len(sx.lstrip())


def correct_indentation(lines):
    waiting = 0
    for l in lines:
        if l.strip():
            if waiting:
                space = " " * indentation(l)
                for i in range(waiting):
                    yield space
                waiting = 0

            yield l
        else:
            waiting += 1


def show(input):
    lines = iter(input)
    lines = correct_indentation(lines)

    def readline(prompt):
        try:
            command = next(lines).rstrip('\n')
        except StopIteration:
            raise EOFError()
        print(prompt, command, sep='')
        return command

    code.interact(readfunc=readline)


if __name__ == "__main__":
    show(fileinput.input())
