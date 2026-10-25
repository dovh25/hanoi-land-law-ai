"""In-memory sliding-window limits for the anonymous demo endpoint.

This is intentionally process-local: the free demo keeps no user state, and the limits
are a cost guard rather than an authorization boundary. The Gemini daily ledger in
``backend/services/llm.py`` remains the authoritative spend cap.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after: int
    remaining: int
    limit: int


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float):
        if limit < 1 or window_seconds <= 0:
            raise ValueError("Invalid rate limit configuration")
        self.limit = limit
        self.window = float(window_seconds)
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> RateDecision:
        current = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.setdefault(key, deque())
            cutoff = current - self.window
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry = max(1, int(events[0] + self.window - current) + 1)
                return RateDecision(False, retry, 0, self.limit)
            events.append(current)
            # Opportunistically drop idle keys so a long-running process stays bounded.
            if len(self._events) > 2048:
                for candidate in [k for k, value in self._events.items() if not value][:1024]:
                    self._events.pop(candidate, None)
            return RateDecision(True, 0, max(0, self.limit - len(events)), self.limit)


class DemoRateLimiter:
    def __init__(self, per_minute: int, per_day: int):
        self.minute = SlidingWindowLimiter(per_minute, 60)
        self.day = SlidingWindowLimiter(per_day, 86400)

    def check(self, key: str) -> RateDecision:
        minute = self.minute.check(key)
        if not minute.allowed:
            return minute
        day = self.day.check(key)
        if not day.allowed:
            return day
        return RateDecision(True, 0, min(minute.remaining, day.remaining), min(minute.limit, day.limit))
