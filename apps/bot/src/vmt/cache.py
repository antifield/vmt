"""transcript and translation caches, keyed off the audio attachment's checksum"""

import hashlib
import logging
from datetime import UTC, datetime

from vmt.db import Database

log = logging.getLogger(__name__)


def checksum_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Cache:
    def __init__(self, db: Database):
        self.db = db

    async def get_transcript(self, checksum: str) -> tuple[str, str] | None:
        """look up a cached (transcript, provider) by checksum, None if we've never seen it"""
        rows = await self.db.execute(
            "SELECT transcript, provider FROM transcript_cache WHERE checksum = ?",
            (checksum,),
        )
        # never log the transcript itself, just whether we found one
        if not rows:
            log.debug("transcript cache miss for %s", checksum[:8])
            return None
        log.debug("transcript cache hit for %s", checksum[:8])
        return rows[0][0], rows[0][1]

    async def store_transcript(
        self, checksum: str, transcript: str, provider: str, duration_secs: float
    ) -> None:
        await self.db.execute(
            """
            INSERT OR REPLACE INTO transcript_cache
                (checksum, transcript, provider, duration_secs, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (checksum, transcript, provider, duration_secs, _now()),
        )

    async def get_translation(self, checksum: str, target_lang: str) -> str | None:
        rows = await self.db.execute(
            """
            SELECT translated FROM translation_cache
            WHERE checksum = ? AND target_lang = ?
            """,
            (checksum, target_lang),
        )
        hit = bool(rows)
        log.debug(
            "translation cache %s for %s -> %s",
            "hit" if hit else "miss",
            checksum[:8],
            target_lang,
        )
        return rows[0][0] if rows else None

    async def store_translation(
        self, checksum: str, target_lang: str, translated: str
    ) -> None:
        await self.db.execute(
            """
            INSERT OR REPLACE INTO translation_cache
                (checksum, target_lang, translated, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (checksum, target_lang, translated, _now()),
        )
