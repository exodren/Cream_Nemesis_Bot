from __future__ import annotations

import time
from collections import defaultdict

_last_action: dict[str, float] = defaultdict(float)


def allow(key: str, cooldown_sec: float) -> bool:
    now = time.monotonic()
    last = _last_action[key]
    if now - last < cooldown_sec:
        return False
    _last_action[key] = now
    return True


def seconds_left(key: str, cooldown_sec: float) -> int:
    now = time.monotonic()
    last = _last_action[key]
    left = cooldown_sec - (now - last)
    return max(0, int(left) + 1)
