# bot/services/mod_logging.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import discord

logger = logging.getLogger(__name__)

_INSERT_MOD_LOG_SQL = """
INSERT INTO moderation_logs
(action, target_id, target_name, moderator_id, moderator_name, reason, timestamp, success, note)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

@dataclass
class ModLogResult:
    db_ok: bool
    db_rowid: Optional[int]
    db_error: Optional[str]
    modlog_ok: bool
    modlog_error: Optional[str]


async def log_moderation_action(
    bot: discord.Client | discord.Bot,
    *,
    action: str,
    target_id: int,
    target_name: str,
    moderator_id: int,
    moderator_name: str,
    reason: Optional[str],
    success: bool,
    note: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> ModLogResult:
    ts = timestamp or int(datetime.utcnow().timestamp())

    # 1) DB insert
    db_ok = False
    db_rowid: Optional[int] = None
    db_error: Optional[str] = None
    try:
        db = getattr(bot, "db", None)
        if db is None:
            db_error = "DB not initialized on bot"
            logger.debug("log_moderation_action: no db on bot")
        else:
            params = (
                action,
                target_id,
                target_name,
                moderator_id,
                moderator_name,
                reason or "",
                ts,
                1 if success else 0,
                note or "",
            )
            rowid = await db.execute(_INSERT_MOD_LOG_SQL, params)
            if rowid is not None:
                db_ok = True
                db_rowid = rowid
            else:
                db_error = "db.execute returned None"
                logger.debug("log_moderation_action: execute returned None")
    except Exception as exc:
        db_error = f"{exc!r}"
        logger.exception("log_moderation_action: DB insert failed")

    # 2) Post embed to mod-log channel
    modlog_ok = False
    modlog_error: Optional[str] = None
    try:
        mod_channel_id = getattr(getattr(bot, "settings", None), "mod_log_channel_id", None)
        if mod_channel_id:
            channel = bot.get_channel(mod_channel_id)
            if channel is None:
                try:
                    # use client fetch which may raise Permission/HTTP errors
                    channel = await bot.fetch_channel(mod_channel_id)
                except Exception:
                    channel = None

            if channel is not None:
                embed = discord.Embed(
                    title=f"Moderation: {action.capitalize()}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow(),
                )
                embed.add_field(name="Target", value=f"{target_name} (`{target_id}`)", inline=False)
                embed.add_field(name="Moderator", value=f"{moderator_name} (`{moderator_id}`)", inline=False)
                embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
                embed.add_field(name="Success", value=str(success), inline=True)
                if note:
                    embed.add_field(name="Note", value=note, inline=False)
                if db_error:
                    embed.add_field(name="DB note", value=db_error, inline=False)

                try:
                    await channel.send(embed=embed)
                    modlog_ok = True
                except Exception as e:
                    modlog_error = f"Failed sending to channel: {e!r}"
                    logger.exception("log_moderation_action: failed to send embed to channel %s", mod_channel_id)
            else:
                modlog_error = f"mod_log_channel_id={mod_channel_id} not found"
                logger.debug("log_moderation_action: mod log channel not found: %s", mod_channel_id)
        else:
            modlog_error = "mod_log_channel_id not configured"
            logger.debug("log_moderation_action: mod_log_channel_id not configured")
    except Exception as e:
        modlog_error = f"{e!r}"
        logger.exception("log_moderation_action: unexpected error when posting modlog")

    return ModLogResult(
        db_ok=db_ok,
        db_rowid=db_rowid,
        db_error=db_error,
        modlog_ok=modlog_ok,
        modlog_error=modlog_error,
    )