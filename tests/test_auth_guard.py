"""
Tests for tools/auth_guard.py — the login brute-force guard (issue: login had
no rate limit or delay). Uses an injected fake clock so no real waiting.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.auth_guard import LoginRateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_not_locked_out_initially():
    rl = LoginRateLimiter(max_failures=3, window_secs=900, clock=FakeClock())
    assert not rl.locked_out("1.2.3.4")


def test_locks_out_after_max_failures():
    clock = FakeClock()
    rl = LoginRateLimiter(max_failures=3, window_secs=900, clock=clock)
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert not rl.locked_out("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert rl.locked_out("1.2.3.4")


def test_lockout_is_per_key():
    clock = FakeClock()
    rl = LoginRateLimiter(max_failures=2, window_secs=900, clock=clock)
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert rl.locked_out("1.2.3.4")
    assert not rl.locked_out("5.6.7.8")


def test_lockout_expires_after_window():
    clock = FakeClock()
    rl = LoginRateLimiter(max_failures=2, window_secs=900, clock=clock)
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert rl.locked_out("1.2.3.4")
    clock.now += 901  # slide past the window
    assert not rl.locked_out("1.2.3.4")


def test_old_failures_slide_out_of_window():
    clock = FakeClock()
    rl = LoginRateLimiter(max_failures=3, window_secs=900, clock=clock)
    rl.record_failure("1.2.3.4")    # t=1000
    clock.now += 899                # t=1899: first failure still inside window
    rl.record_failure("1.2.3.4")    # [1000, 1899]
    clock.now += 2                  # t=1901: failure from t=1000 is 901s old → expired
    rl.record_failure("1.2.3.4")    # prune drops it → [1899, 1901] = 2 < 3
    assert not rl.locked_out("1.2.3.4")
    rl.record_failure("1.2.3.4")    # 3 in window
    assert rl.locked_out("1.2.3.4")


def test_reset_clears_failures():
    clock = FakeClock()
    rl = LoginRateLimiter(max_failures=2, window_secs=900, clock=clock)
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert rl.locked_out("1.2.3.4")
    rl.reset("1.2.3.4")
    assert not rl.locked_out("1.2.3.4")


def test_reset_on_unknown_key_is_safe():
    rl = LoginRateLimiter(clock=FakeClock())
    rl.reset("never-seen")
    assert not rl.locked_out("never-seen")
