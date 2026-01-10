# bot/db.py
from __future__ import annotations

import aiosqlite
import logging
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER NOT NULL UNIQUE,
    username TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
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
        logger.info("Bootstrapping DB schema")
        conn = self._ensure_conn()
        await conn.executescript(schema_sql)
        await conn.commit()
        logger.info("DB schema bootstrapped")

    async def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> None:
        conn = self._ensure_conn()
        await conn.execute(sql, params or [])
        await conn.commit()

    async def fetchone(self, sql: str, params: Optional[Iterable[Any]] = None) -> Optional[aiosqlite.Row]:
        conn = self._ensure_conn()
        cur = await conn.execute(sql, params or [])
        row = await cur.fetchone()
        await cur.close()
        return row