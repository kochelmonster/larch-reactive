# for ccore.pyx to ensure that decorated functions are pure python functions
def _make_handler(context, func):
    def handler(*args, **kwargs):
        return context.call(func, *args, **kwargs)

    return handler
