"""tracks how many seconds of audio each user has burned through today, per utc day"""

from datetime import UTC, datetime

from vmt.db import Database


def utc_today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class UsageTracker:
    def __init__(self, db: Database, daily_limit_seconds: float = 0):
        self.db = db
        self.daily_limit_seconds = daily_limit_seconds

    @property
    def unlimited(self) -> bool:
        return not self.daily_limit_seconds

    async def seconds_used(self, user_id: int, day: str | None = None) -> float:
        day = day or utc_today()
        rows = await self.db.execute(
            "SELECT seconds_used FROM usage_daily WHERE user_id = ? AND day = ?",
            (user_id, day),
        )
        return float(rows[0][0]) if rows else 0.0

    async def check_quota(
        self, user_id: int, duration_secs: float, day: str | None = None
    ) -> tuple[bool, float | None]:
        """can this user use duration_secs more? remaining is None when there's no limit"""
        if self.unlimited:
            return True, None
        used = await self.seconds_used(user_id, day)
        remaining = max(self.daily_limit_seconds - used, 0.0)
        return duration_secs <= remaining, remaining

    async def totals(self) -> tuple[int, float]:
        """lifetime clips and seconds across everyone, for the stats page"""
        rows = await self.db.execute(
            "SELECT COALESCE(SUM(total_requests), 0), COALESCE(SUM(total_seconds), 0) FROM users"
        )
        if not rows:
            return 0, 0.0
        return int(rows[0][0]), float(rows[0][1])

    async def record_usage(
        self,
        user_id: int,
        duration_secs: float,
        day: str | None = None,
        now: datetime | None = None,
    ) -> None:
        day = day or utc_today()
        timestamp = (now or datetime.now(UTC)).isoformat()
        await self.db.execute(
            """
            INSERT INTO usage_daily (user_id, day, seconds_used, requests)
            VALUES (?, ?, ?, 1)
            ON CONFLICT (user_id, day) DO UPDATE SET
                seconds_used = seconds_used + excluded.seconds_used,
                requests = requests + 1
            """,
            (user_id, day, duration_secs),
        )
        await self.db.execute(
            """
            INSERT INTO users
                (user_id, first_seen, last_seen, total_requests, total_seconds)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                total_requests = total_requests + 1,
                total_seconds = total_seconds + excluded.total_seconds
            """,
            (user_id, timestamp, timestamp, duration_secs),
        )
