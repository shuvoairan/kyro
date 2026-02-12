from __future__ import annotations

import logging
from typing import Optional, List, Dict, Tuple

import discord
from discord import app_commands, Interaction
from discord.ext import commands
from bot.services.time import now_ts, format_dt, format_duration

logger = logging.getLogger(__name__)


_INSERT_AFk_SQL = "REPLACE INTO afk_statuses (user_id, reason, since) VALUES (?, ?, ?);"
_DELETE_AFK_SQL = "DELETE FROM afk_statuses WHERE user_id = ?;"
_SELECT_AFK_SQL = "SELECT user_id, reason, since FROM afk_statuses WHERE user_id = ?;"
_SELECT_ALL_AFK_SQL = "SELECT user_id, reason, since FROM afk_statuses ORDER BY since DESC;"


class UserAfkCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


    @app_commands.command(name="afk", description="Set your AFK status (reason optional).")
    @app_commands.describe(reason="Why you're AFK (optional)")
    async def afk(
        self,
        interaction: Interaction,
        reason: Optional[str] = None,
    ) -> None:
        user = interaction.user
        ts = now_ts()
        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.response.send_message("Database not available - AFK not set.", ephemeral=True)
            return

        try:
            await db.execute(_INSERT_AFk_SQL, (user.id, reason or "No reason provided.", ts))
        except Exception:
            logger.exception("Failed to insert AFK for %s", user.id)
            await interaction.response.send_message("Failed to set AFK - see logs.", ephemeral=True)
            return

        reply = f"✅ {user.mention}, I set your AFK status."
        if reason:
            reply += f" Reason: {reason}"
        reply += f" (since {format_dt(ts)})"
        await interaction.response.send_message(reply, ephemeral=True)

    @app_commands.command(name="afk_list", description="Show who is currently AFK.")
    async def afk_list(self, interaction: Interaction) -> None:
        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.response.send_message("Database not available.", ephemeral=True)
            return

        try:
            rows = await db.fetchall(_SELECT_ALL_AFK_SQL)
        except Exception:
            logger.exception("Failed to fetch AFK list")
            await interaction.response.send_message("Failed to query AFK list.", ephemeral=True)
            return

        if not rows:
            await interaction.response.send_message("No users are currently AFK.", ephemeral=True)
            return

        lines: List[str] = []
        resolved: Dict[int, Optional[str]] = {}
        for r in rows[:100]:
            uid = int(r["user_id"])
            reason = r["reason"]
            since = int(r["since"])
            try:
                u = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                name = f"{u}"
            except Exception:
                name = str(uid)
            resolved[uid] = name
            lines.append(f"• **{name}** - {reason} - since {format_dt(since)} ({format_duration(since)})")

        embed = discord.Embed(
            title="AFK users",
            description="\n".join(lines[:50]),
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Total AFK: {len(rows)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Event listeners ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore bot messages
        if message.author.bot:
            return

        # If author was AFK, remove AFK and announce "welcome back"
        db = getattr(self.bot, "db", None)
        if db is None:
            return

        author_id = message.author.id
        try:
            row = await db.fetchone(_SELECT_AFK_SQL, (author_id,))
        except Exception:
            logger.exception("Failed to check AFK status for author %s", author_id)
            row = None

        if row is not None:
            # remove AFK
            try:
                await db.execute(_DELETE_AFK_SQL, (author_id,))
            except Exception:
                logger.exception("Failed to remove AFK for %s", author_id)

            since = int(row["since"])
            duration = format_duration(since)
            last_seen = format_dt(since)

            try:
                if message.guild:
                    await message.channel.send(f"Welcome back {message.author.mention}! You were AFK since {last_seen} (duration {duration}).")
                # attempt DM as well
                try:
                    await message.author.send(f"You are no longer AFK - welcome back! You were AFK since {last_seen} (duration {duration}).")
                except Exception:
                    # DM may be closed
                    logger.debug("Could not DM user %s after AFK removal", author_id, exc_info=True)
            except Exception:
                logger.exception("Failed to announce AFK removal for %s", author_id)

        if not message.mentions:
            return

        mentioned_ids = {u.id for u in message.mentions if not u.bot}
        if not mentioned_ids:
            return

        afk_rows: Dict[int, Tuple[str, int]] = {}
        try:
            for uid in mentioned_ids:
                r = await db.fetchone(_SELECT_AFK_SQL, (uid,))
                if r is not None:
                    afk_rows[uid] = (r["reason"] or "No reason provided", int(r["since"]))
        except Exception:
            logger.exception("Error fetching AFK statuses for mentions")

        if not afk_rows:
            return

        parts: List[str] = []
        for uid, (reason, since) in afk_rows.items():
            try:
                u = message.guild.get_member(uid) if message.guild else None
                display = f"{u.display_name}"
            except Exception:
                display = f"`{uid}`"
            parts.append(f"**{display}** is AFK - {reason} - since {format_dt(since)}")

        reply_text = "\n".join(parts)
        try:
            await message.channel.send(reply_text)
        except Exception:
            logger.exception("Failed to send AFK mention replies for message %s", getattr(message, "id", None))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserAfkCog(bot))
