import pytest

from vmt.services.retry import retry_with_backoff


async def _no_sleep(_seconds):
    # test double, skip the actual waiting
    pass


async def test_retries_until_success():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("boom")
        return "ok"

    result = await retry_with_backoff(
        flaky, should_retry=lambda exc: True, sleep=_no_sleep
    )
    assert result == "ok"
    assert calls == 3


async def test_gives_up_after_max_attempts():
    calls = 0

    async def always_fails():
        nonlocal calls
        calls += 1
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        await retry_with_backoff(
            always_fails, should_retry=lambda exc: True, attempts=3, sleep=_no_sleep
        )
    assert calls == 3


async def test_does_not_retry_when_should_retry_says_no():
    calls = 0

    async def bad_input():
        nonlocal calls
        calls += 1
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await retry_with_backoff(
            bad_input, should_retry=lambda exc: False, sleep=_no_sleep
        )
    assert calls == 1


async def test_backoff_delays_double_each_time():
    delays = []

    async def _record_sleep(seconds):
        delays.append(seconds)

    calls = 0

    async def always_fails():
        nonlocal calls
        calls += 1
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        await retry_with_backoff(
            always_fails,
            should_retry=lambda exc: True,
            attempts=3,
            base_delay=1.0,
            sleep=_record_sleep,
        )
    assert delays == [1.0, 2.0]
