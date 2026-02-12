from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict

import discord
from discord import app_commands, Interaction
from discord.ext import commands

from bot.services.time import now_ts

logger = logging.getLogger(__name__)

_INSERT_CONFESSION_SQL = "INSERT INTO confessions (content, category, timestamp) VALUES (?, ?, ?);"
_UPDATE_CONFESSION_MESSAGE_SQL = "UPDATE confessions SET message_id = ? WHERE id = ?;"
_MARK_CONFESSION_DELETED_SQL = "UPDATE confessions SET deleted = 1 WHERE id = ?;"
_SELECT_CONFESSION_SQL = "SELECT id, content, category, timestamp, message_id, deleted FROM confessions WHERE id = ?;"
_SELECT_RECENT_CONFESSIONS_SQL = "SELECT id, content, category, timestamp, message_id, deleted FROM confessions ORDER BY timestamp DESC LIMIT ?;"

# categories visible to users
CONFESSION_CATEGORIES = [
    app_commands.Choice(name="Love", value="love"),
    app_commands.Choice(name="Secret", value="secret"),
    app_commands.Choice(name="Rant", value="rant"),
    app_commands.Choice(name="Question", value="question"),
    app_commands.Choice(name="Other", value="other"),
]


def _truncate(s: str, limit: int = 800) -> str:
    if len(s) <= limit:
        return s
    return s[: limit - 3].rstrip() + "..."


class UserConfessionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # in-memory rate limit map: user_id -> last_ts
        self._last_confess: Dict[int, int] = {}
        self._rate_lock = asyncio.Lock()
        # default rate limit seconds (fallback)
        self._default_rate_seconds = 300

    def _get_confession_channel_id(self) -> Optional[int]:
        return getattr(getattr(self.bot, "settings", None), "confession_channel_id", None)

    def _get_rate_limit_seconds(self) -> int:
        s = getattr(getattr(self.bot, "settings", None), "confession_rate_limit_seconds", None)
        try:
            return int(s) if s is not None else self._default_rate_seconds
        except Exception:
            return self._default_rate_seconds

    def _is_moderator(self, interaction: Interaction) -> bool:
        settings = getattr(self.bot, "settings", None)
        mod_role_id = getattr(settings, "mod_role_id", None) if settings else None
        if mod_role_id and interaction.guild:
            role = interaction.guild.get_role(mod_role_id)
            return role in interaction.user.roles if role else False
        return interaction.user.guild_permissions.manage_messages


    @app_commands.command(name="confess", description="Send an anonymous confession")
    @app_commands.describe(category="Choose a confession category", message="Your confession message (max 1500 chars)")
    @app_commands.choices(category=CONFESSION_CATEGORIES)
    async def confess(
        self,
        interaction: Interaction,
        category: app_commands.Choice[str],
        message: str,
    ) -> None:
        # Basic validation
        if not message or not message.strip():
            await interaction.response.send_message("Please provide a non-empty confession.", ephemeral=True)
            return
        if len(message) > 1500:
            await interaction.response.send_message("Confession is too long (max 1500 characters).", ephemeral=True)
            return

        rate_seconds = self._get_rate_limit_seconds()
        now = now_ts()
        async with self._rate_lock:
            last = self._last_confess.get(interaction.user.id)
            if last is not None and (now - last) < rate_seconds:
                remaining = rate_seconds - (now - last)
                await interaction.response.send_message(
                    f"You may only send one confession every {rate_seconds // 60} minutes. Try again in {remaining}s.",
                    ephemeral=True,
                )
                return
            # tentatively record now
            # will update after DB/POST success
            self._last_confess[interaction.user.id] = now

        db = getattr(self.bot, "db", None)
        if db is None:
            async with self._rate_lock:
                self._last_confess.pop(interaction.user.id, None)
            await interaction.response.send_message("Database is not available. Please contact a mod.", ephemeral=True)
            return

        try:
            rowid = await db.execute(_INSERT_CONFESSION_SQL, (message, category.value, now))
            confession_id = int(rowid) if rowid is not None else None
        except Exception:
            # rollback rate-limit on failure
            async with self._rate_lock:
                self._last_confess.pop(interaction.user.id, None)
            logger.exception("UserConfessionsCog: failed to insert confession")
            await interaction.response.send_message("Failed to save your confession. Please contact a mod.", ephemeral=True)
            return

        # Resolve confession channel
        ch_id = self._get_confession_channel_id()
        if not ch_id:
            # We don't store user id, but we must roll back DB entry? We'll keep the DB row but mark as message_id NULL.
            await interaction.response.send_message(
                "Confession channel is not configured. Ask an admin to set 'confession_channel_id' in settings.", ephemeral=True
            )
            return

        # Post to confession channel
        channel: Optional[discord.abc.Messageable] = self.bot.get_channel(ch_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ch_id)
            except Exception:
                channel = None

        embed = discord.Embed(
            title=f"Confession{f' #{confession_id}' if confession_id else ''}",
            description=_truncate(message, 1900),
            color=discord.Color.dark_teal(),
        )
        embed.add_field(name="Category", value=category.name, inline=True)

        posted_msg_id: Optional[int] = None
        if channel is not None and isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.abc.Messageable)):
            try:
                sent = await channel.send(embed=embed)
                posted_msg_id = getattr(sent, "id", None)
            except Exception:
                logger.exception("UserConfessionsCog: failed to post confession to channel id %s", ch_id)
        else:
            logger.warning("UserConfessionsCog: confession channel id %s not resolvable", ch_id)

        # Update DB with message_id if we have it
        if confession_id and posted_msg_id:
            try:
                await db.execute(_UPDATE_CONFESSION_MESSAGE_SQL, (posted_msg_id, confession_id))
            except Exception:
                logger.exception("UserConfessionsCog: failed to update confession message_id for %s", confession_id)

        try:
            await interaction.response.send_message("✅ Your anonymous confession has been posted.", ephemeral=True)
        except Exception:
            # If the initial response failed (shouldn't normally) just log
            logger.debug("UserConfessionsCog: failed to send ephemeral confirmation", exc_info=True)


    confessions = app_commands.Group(name="confessions", description="Moderation: manage confessions")

    @confessions.command(name="remove", description="Mark confession as deleted and remove message from channel (moderator only)")
    @app_commands.describe(confession_id="ID of confession to remove")
    async def remove_confession(self, interaction: Interaction, confession_id: int) -> None:
        if not self._is_moderator(interaction):
            await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
            return

        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.response.send_message("Database not available.", ephemeral=True)
            return

        try:
            row = await db.fetchone(_SELECT_CONFESSION_SQL, (confession_id,))
        except Exception:
            logger.exception("UserConfessionsCog: error querying confession %s", confession_id)
            await interaction.response.send_message("Failed to query confession.", ephemeral=True)
            return

        if not row:
            await interaction.response.send_message(f"Confession #{confession_id} not found.", ephemeral=True)
            return

        # Delete the posted message if known
        msg_id = row["message_id"]
        if msg_id:
            ch_id = self._get_confession_channel_id()
            if ch_id:
                try:
                    ch = self.bot.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
                    if ch and hasattr(ch, "fetch_message"):
                        try:
                            m = await ch.fetch_message(int(msg_id))
                            await m.delete()
                        except discord.NotFound:
                            # already deleted
                            pass
                        except Exception:
                            logger.exception("UserConfessionsCog: failed to delete confession message %s in channel %s", msg_id, ch_id)
                except Exception:
                    logger.exception("UserConfessionsCog: failed resolving confession channel to delete message")
        # Mark as deleted in DB
        try:
            await db.execute(_MARK_CONFESSION_DELETED_SQL, (confession_id,))
        except Exception:
            logger.exception("UserConfessionsCog: failed to mark confession %s as deleted", confession_id)
            await interaction.response.send_message("Failed to delete confession from DB.", ephemeral=True)
            return

        await interaction.response.send_message(f"Confession #{confession_id} marked as deleted.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserConfessionsCog(bot))