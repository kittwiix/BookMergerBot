import sys
import io

def setup_encoding():
    if sys.version_info >= (3, 0):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    else:
        reload(sys)
        sys.setdefaultencoding('utf-8')
setup_encoding()