from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def format_dt(ts: Optional[int]) -> str:
    if ts is None:
        return "Unknown"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return f"{discord.utils.format_dt(dt, style='F')} ({discord.utils.format_dt(dt, style='R')})"
    except Exception:
        return str(ts)


def format_duration(ts_since: int) -> str:
    try:
        delta = datetime.now(timezone.utc) - datetime.fromtimestamp(ts_since, tz=timezone.utc)
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m{secs % 60}s"
        if secs < 86400:
            return f"{secs // 3600}h{(secs % 3600) // 60}m"
        return f"{secs // 86400}d{(secs % 86400) // 3600}h"
    except Exception:
        return "unknown"