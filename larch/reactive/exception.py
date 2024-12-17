import sys
import traceback


def format_full_exception_tb():
    exc_info = sys.exc_info()
    tb = traceback.format_stack()[:-2]
    tb.extend(traceback.format_tb(exc_info[2]))
    tb.extend(traceback.format_exception_only(exc_info[0], exc_info[1]))
    tb_str = "Traceback (most recent call last):\n"
    tb_str += "".join(tb)[:-1]
    return tb_str
