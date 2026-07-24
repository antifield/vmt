"""libsql-backed storage

the libsql driver is sync-only, so every call gets pushed through
asyncio.to_thread and lined up behind one lock - plenty fast for how
small this bot is
"""

import asyncio
import logging
from pathlib import Path

import libsql

log = logging.getLogger(__name__)

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_seen TEXT,
        last_seen TEXT,
        total_requests INTEGER DEFAULT 0,
        total_seconds REAL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_daily (
        user_id INTEGER,
        day TEXT,
        seconds_used REAL DEFAULT 0,
        requests INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, day)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_cache (
        checksum TEXT PRIMARY KEY,
        transcript TEXT,
        provider TEXT,
        duration_secs REAL,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_cache (
        checksum TEXT,
        target_lang TEXT,
        translated TEXT,
        created_at TEXT,
        PRIMARY KEY (checksum, target_lang)
    )
    """,
)


class Database:
    """one connection to libsql, wrapped so the rest of the bot can just await it

    give it sync_url and the local file becomes an embedded replica of the
    remote turso database, otherwise it's just a plain local sqlite file
    """

    def __init__(
        self,
        path: str = "data/vmt.db",
        sync_url: str | None = None,
        auth_token: str | None = None,
    ):
        self._path = path
        self._sync_url = sync_url
        self._auth_token = auth_token
        self._conn = None
        self._lock = asyncio.Lock()

    def _connect_sync(self):
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        if self._sync_url:
            log.info("Connecting to Turso (embedded replica at %s)", self._path)
            conn = libsql.connect(  # pyright: ignore[reportAttributeAccessIssue]
                self._path,
                sync_url=self._sync_url,
                auth_token=self._auth_token or "",
            )
            conn.sync()
        else:
            log.info("Using local database at %s", self._path)
            conn = libsql.connect(self._path)  # pyright: ignore[reportAttributeAccessIssue]
        for statement in SCHEMA:
            conn.execute(statement)
        conn.commit()
        if self._sync_url:
            conn.sync()
        return conn

    async def connect(self) -> None:
        """open the connection and make sure the tables exist, safe to call more than once"""
        async with self._lock:
            self._conn = await asyncio.to_thread(self._connect_sync)

    def _execute_sync(self, sql: str, params: tuple) -> list[tuple]:
        if self._conn is None:
            raise RuntimeError("database used before connect()")
        cursor = self._conn.execute(sql, params)
        rows = cursor.fetchall()
        self._conn.commit()
        if self._sync_url and not sql.lstrip().upper().startswith("SELECT"):
            try:
                self._conn.sync()
            except Exception:
                log.warning(
                    "Turso sync failed, continuing with local replica", exc_info=True
                )
        return rows

    async def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        """run one statement, get back every row"""
        if self._conn is None:
            raise RuntimeError("Database.connect() has not been called")
        async with self._lock:
            return await asyncio.to_thread(self._execute_sync, sql, params)

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await asyncio.to_thread(self._conn.close)
                self._conn = None
