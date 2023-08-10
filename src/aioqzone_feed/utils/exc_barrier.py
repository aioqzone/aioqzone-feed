import sys

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup


class ExcBarrier:
    def __init__(self, max_len: int = 5) -> None:
        self._exc = []  # type: list[Exception]
        self.max_len = max_len

    def append(self, e: Exception):
        self._exc.append(e)
        if len(self._exc) >= self.max_len:
            raise ExceptionGroup("max retry exceeds", self._exc)
