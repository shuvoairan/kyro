from __future__ import annotations

import aiosqlite
import logging
from pathlib import Path
from typing import Any, Iterable, Optional, List

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS moderation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    target_name TEXT NOT NULL,
    moderator_id INTEGER NOT NULL,
    moderator_name TEXT NOT NULL,
    reason TEXT,
    timestamp INTEGER NOT NULL,
    success INTEGER NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS guild_members (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    nickname TEXT,
    first_joined_at INTEGER NOT NULL,
    last_joined_at INTEGER NOT NULL,
    left_at INTEGER
);
    
CREATE TABLE IF NOT EXISTS afk_statuses (
    user_id INTEGER PRIMARY KEY,
    reason TEXT,
    since INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        logger.info("Opening sqlite database at %s", self.path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.commit()
        logger.debug("Database connection established")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.debug("Database connection closed")

    def _ensure_conn(self) -> aiosqlite.Connection:
        if not self._conn:
            raise RuntimeError("Database connection is not open. Call connect() first.")
        return self._conn

    async def bootstrap(self, schema_sql: str = DEFAULT_SCHEMA) -> None:
        """Create DB schema (gets called on every startup)."""
        logger.info("Bootstrapping DB schema")
        conn = self._ensure_conn()
        await conn.executescript(schema_sql)
        await conn.commit()
        logger.info("DB schema bootstrapped")

    async def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> Optional[int]:
        conn = self._ensure_conn()
        async with conn.execute(sql, tuple(params or [])) as cur:
            await conn.commit()
            try:
                return cur.lastrowid
            except AttributeError:
                return None

    async def fetchone(self, sql: str, params: Optional[Iterable[Any]] = None) -> Optional[aiosqlite.Row]:
        conn = self._ensure_conn()
        async with conn.execute(sql, tuple(params or [])) as cur:
            row = await cur.fetchone()
            return row

    async def fetchall(self, sql: str, params: Optional[Iterable[Any]] = None) -> List[aiosqlite.Row]:
        conn = self._ensure_conn()
        async with conn.execute(sql, tuple(params or [])) as cur:
            rows = await cur.fetchall()
            return rows
