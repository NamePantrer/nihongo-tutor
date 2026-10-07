from __future__ import annotations

import time


def delay_hours(now: float, last_at: float | None, created_at: float) -> float:
    origin = last_at if last_at is not None else created_at
    return max(0.0, (now - origin) / 3600.0)


def attempt_index(now: float, last_at: float | None, last_index: int | None) -> int:
    """A new first try if the last attempt was more than 2 hours ago."""
    if last_at is None:
        return 1
    if (now - last_at) >= 2 * 3600:
        return 1
    return (last_index or 1) + 1


def review(ease: float, interval_days: float, outcome: str) -> tuple[float, float]:
    """Tiny SM-2. Fail can shorten; pass lengthens. Interval may go below 1 day."""
    ease = max(1.3, min(2.8, ease))
    if outcome == "fail":
        ease = max(1.3, ease - 0.2)
        interval = 0.25
    elif outcome == "partial":
        ease = max(1.3, ease - 0.05)
        interval = max(0.5, interval_days * 1.1 if interval_days else 0.5)
    else:
        ease = min(2.8, ease + 0.05)
        if interval_days < 0.5:
            interval = 1.0
        elif interval_days < 2:
            interval = 3.0
        else:
            interval = round(interval_days * ease, 2)
    return ease, interval


def due_at(now: float, interval_days: float) -> float:
    return now + interval_days * 86400.0


def now() -> float:
    return time.time()
