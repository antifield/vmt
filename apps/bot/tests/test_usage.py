from vmt.usage import UsageTracker

USER = 1234


async def test_quota_allows_within_limit(db):
    tracker = UsageTracker(db, daily_limit_seconds=120)

    allowed, remaining = await tracker.check_quota(USER, 60)
    assert allowed
    assert remaining == 120

    await tracker.record_usage(USER, 60)
    allowed, remaining = await tracker.check_quota(USER, 60)
    assert allowed
    assert remaining == 60


async def test_quota_denies_over_limit(db):
    tracker = UsageTracker(db, daily_limit_seconds=100)

    await tracker.record_usage(USER, 90)
    allowed, remaining = await tracker.check_quota(USER, 30)
    assert not allowed
    assert remaining == 10

    # a shorter clip that fits the remainder is still allowed
    allowed, _ = await tracker.check_quota(USER, 10)
    assert allowed


async def test_quota_exhausted_remaining_clamped_to_zero(db):
    tracker = UsageTracker(db, daily_limit_seconds=50)

    await tracker.record_usage(USER, 40)
    await tracker.record_usage(USER, 40)

    allowed, remaining = await tracker.check_quota(USER, 1)
    assert not allowed
    assert remaining == 0.0


async def test_unlimited_when_limit_unset(db):
    tracker = UsageTracker(db, daily_limit_seconds=0)

    allowed, remaining = await tracker.check_quota(USER, 10_000_000)
    assert allowed
    assert remaining is None


async def test_utc_day_rollover_resets_quota(db):
    tracker = UsageTracker(db, daily_limit_seconds=60)

    await tracker.record_usage(USER, 60, day="2026-07-24")
    allowed, remaining = await tracker.check_quota(USER, 1, day="2026-07-24")
    assert not allowed
    assert remaining == 0.0

    # the next utc day starts a fresh bucket
    allowed, remaining = await tracker.check_quota(USER, 1, day="2026-07-25")
    assert allowed
    assert remaining == 60


async def test_usage_isolated_per_user(db):
    tracker = UsageTracker(db, daily_limit_seconds=60)

    await tracker.record_usage(USER, 60)
    allowed, _ = await tracker.check_quota(USER + 1, 30)
    assert allowed


async def test_record_usage_updates_user_rollups(db):
    tracker = UsageTracker(db, daily_limit_seconds=0)

    await tracker.record_usage(USER, 10)
    await tracker.record_usage(USER, 20)

    rows = await db.execute(
        "SELECT total_requests, total_seconds, first_seen, last_seen "
        "FROM users WHERE user_id = ?",
        (USER,),
    )
    total_requests, total_seconds, first_seen, last_seen = rows[0]
    assert total_requests == 2
    assert total_seconds == 30
    assert first_seen <= last_seen
