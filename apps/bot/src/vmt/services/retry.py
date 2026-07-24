"""tiny retry helper for flaky external api calls, no new deps"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 1.0


async def retry_with_backoff[T](
    func: Callable[[], Awaitable[T]],
    *,
    should_retry: Callable[[Exception], bool],
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    label: str = "call",
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """call func, and if it blows up with something worth retrying, try again with a longer wait each time

    attempts=3 means up to 3 tries total, waiting base_delay then base_delay*2 between them.
    should_retry decides what's worth retrying (rate limits, 5xx, dropped connections) vs
    what should just fail right away (bad auth, bad input).
    """
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:
            if attempt == attempts or not should_retry(exc):
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log.warning(
                "%s failed (attempt %d/%d), retrying in %.0fs: %s",
                label,
                attempt,
                attempts,
                delay,
                exc,
            )
            await sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
