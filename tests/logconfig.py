import io
import logging

logstream = io.StringIO()
level = logging.DEBUG

log_format = ("> %(created)f %(levelname)s %(name)s"
              " %(pathname)s(%(lineno)d): %(message)s")
logging.basicConfig(level=level, format=log_format, stream=logstream)
logging.captureWarnings(True)
