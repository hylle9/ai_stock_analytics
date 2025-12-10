import time
from contextlib import contextmanager

class Timer:
    """
    Context manager for timing code execution.
    Usage:
        with Timer("Task Name"):
            do_something()
    """
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        
    def __enter__(self):
        self.start = time.perf_counter()
        return self
        
    def __exit__(self, *args):
        if self.enabled:
            elapsed = (time.perf_counter() - self.start) * 1000
            print(f"⏱️ [PROF] {self.name}: {elapsed:.2f} ms")

@contextmanager
def simple_timer(name):
    t0 = time.perf_counter()
    yield
    t1 = time.perf_counter()
    print(f"⏱️ [PROF] {name}: {(t1-t0)*1000:.2f} ms")
