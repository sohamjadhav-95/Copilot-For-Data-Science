"""
Utility helpers: retry decorator, timer, human-like delay.
"""

import asyncio
import functools
import random
import time
from typing import TypeVar, Callable, Any

from loguru import logger

T = TypeVar("T")


# ── Retry with exponential backoff ────────────────────────────────────────────

def async_retry(
    attempts: int = 3,
    backoff_base: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """Decorator: retry an async function with exponential backoff + jitter."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < attempts:
                        delay = backoff_base ** attempt + random.uniform(0, 1)
                        logger.warning(
                            f"[Retry {attempt}/{attempts}] {func.__name__} "
                            f"failed: {exc!r} — retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"[Retry {attempt}/{attempts}] {func.__name__} "
                            f"failed permanently: {exc!r}"
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ── Timer context manager ────────────────────────────────────────────────────

class Timer:
    """Simple context-manager timer that records elapsed milliseconds."""

    def __init__(self) -> None:
        self.start: float = 0
        self.end: float = 0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.end = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((self.end - self.start) * 1000)


# ── Human-like delay ─────────────────────────────────────────────────────────

async def human_delay(min_ms: int = 50, max_ms: int = 200) -> None:
    """Sleep for a random duration to mimic human interaction."""
    await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)
