"""
In-memory brute-force guard for the admin login endpoint (single-process app).
"""

import time
from collections import deque
from typing import Callable, Dict, Deque


class LoginRateLimiter:
    """Per-key failure tracker with a sliding-window lockout.

    In-memory only: correct for this single-process FastAPI app; would need a
    shared store (e.g. Redis) if the app ever runs multiple workers.
    """

    def __init__(self, max_failures: int = 5, window_secs: float = 900.0,
                 clock: Callable[[], float] = time.time):
        self.max_failures = max_failures
        self.window_secs = window_secs
        self._clock = clock
        self._failures: Dict[str, Deque[float]] = {}

    def locked_out(self, key: str) -> bool:
        self._prune(key)
        return len(self._failures.get(key, deque())) >= self.max_failures

    def record_failure(self, key: str) -> None:
        self._prune(key)
        self._failures.setdefault(key, deque()).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def _prune(self, key: str) -> None:
        q = self._failures.get(key)
        if q:
            cutoff = self._clock() - self.window_secs
            while q and q[0] < cutoff:
                q.popleft()
