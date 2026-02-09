from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import View, Button

logger = logging.getLogger(__name__)


class UserCommandCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="avatar", description="Display a user's avatar")
    @app_commands.describe(user="User to display avatar for (defaults to you)")
    async def avatar(
        self,
        interaction: Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        # Use the provided user or fallback to command invoker
        member = user or interaction.user  # type: ignore[assignment]

        # Use display_avatar to prefer guild avatar if available
        asset: discord.Asset = member.display_avatar

        # Build URLs for the formats we want. with_format may raise for some combinations,
        # so we wrap in try/except and gracefully fallback to the default .url.
        def build_url(fmt: str) -> str:
            try:
                return str(asset.with_format(fmt).with_size(1024).url)
            except Exception:
                try:
                    return str(asset.with_format(fmt).url)
                except Exception:
                    # final fallback (shouldn't normally be hit)
                    return str(asset.url)

        png_url = build_url("png")
        jpg_url = build_url("jpeg")
        webp_url = build_url("webp")
        gif_url = None
        try:
            if getattr(asset, "is_animated", lambda: False)():
                gif_url = build_url("gif")
        except Exception:
            gif_url = None

        try:
            preview_url = str(asset.with_size(4096).url)
        except Exception:
            preview_url = str(asset.url)

        embed = discord.Embed(
            title=f"{member.display_name}'s avatar",
            color=discord.Color.blurple(),
        )
        embed.set_image(url=preview_url)

        # Build a view with link buttons (link buttons don't require special permissions)
        view = View()
        view.add_item(Button(label="PNG", url=png_url, style=discord.ButtonStyle.link))
        view.add_item(Button(label="JPG", url=jpg_url, style=discord.ButtonStyle.link))
        view.add_item(Button(label="WebP", url=webp_url, style=discord.ButtonStyle.link))
        if gif_url:
            view.add_item(Button(label="GIF", url=gif_url, style=discord.ButtonStyle.link))

        # Send the embed and buttons
        try:
            await interaction.response.send_message(embed=embed, view=view)
        except Exception as exc:
            logger.exception("Failed to send avatar response for %s: %s", member, exc)
            # Attempt a fallback ephemeral message to the invoker
            try:
                await interaction.response.send_message(
                    "Failed to show avatar - check bot permissions or logs.", ephemeral=True
                )
            except Exception:
                logger.debug("Could not send fallback ephemeral message for avatar command", exc_info=True)

    @app_commands.command(name="userinfo", description="Display detailed information about a user")
    @app_commands.describe(user="User to display information for (defaults to you)")
    async def userinfo(
        self,
        interaction: Interaction,
        user: Optional[discord.User] = None,
    ) -> None:
        target: discord.abc.User = user or interaction.user  # type: ignore[assignment]

        member: Optional[discord.Member] = None
        if interaction.guild is not None:
            try:
                member = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)
            except Exception:
                member = None

        def fmt(dt: Optional[discord.datetime.datetime]) -> str:
            if not dt:
                return "Unknown"
            try:
                # Full datetime + relative
                return f"{discord.utils.format_dt(dt, style='F')} ({discord.utils.format_dt(dt, style='R')})"
            except Exception:
                return str(dt)

        roles_str = "No roles"
        if member is not None:
            roles = [r for r in member.roles if r.name != "@everyone"]
            roles = sorted(roles, key=lambda r: r.position, reverse=True)
            if roles:
                roles_mentions = " ".join(r.mention for r in roles)
                # Discord embed field limit is 1024; truncate gracefully if needed
                if len(roles_mentions) > 1000:
                    # show first few role mentions and collapse the rest
                    short = []
                    cum = 0
                    for r in roles:
                        if cum + len(r.name) + 1 > 800:
                            break
                        short.append(r.mention)
                        cum += len(r.name) + 1
                    remaining = len(roles) - len(short)
                    roles_str = " ".join(short) + (f" and {remaining} more" if remaining else "")
                else:
                    roles_str = roles_mentions
            else:
                roles_str = "No roles"

        # Presence / status
        status = "Unknown"
        activities: list[discord.BaseActivity] = []
        if member is not None:
            try:
                status = str(member.status).title() if getattr(member, "status", None) is not None else "Offline"
            except Exception:
                status = "Unknown"

            try:
                activities = list(member.activities or [])
            except Exception:
                activities = []

        if activities:
            activity_lines: list[str] = []
            for act in activities:
                try:
                    kind = getattr(act, "type", None)
                    kind_name = getattr(kind, "name", None)
                    if kind_name is None and isinstance(act, discord.CustomActivity):
                        label = "Custom"
                    else:
                        label = (kind_name or getattr(act, "type", str(act))).title()

                    description = ""
                    if getattr(act, "name", None):
                        description = str(act.name)
                    if getattr(act, "state", None):
                        description = f"{description} - {act.state}" if description else str(act.state)
                    if getattr(act, "details", None):
                        description = f"{description} - {act.details}" if description else str(act.details)

                    if getattr(act, "url", None):
                        description = f"{description} ({act.url})" if description else str(act.url)

                    if not description:
                        description = repr(act)

                    activity_lines.append(f"**{label}**: {description}")
                except Exception:
                    activity_lines.append(repr(act))

            activity_str = "\n".join(activity_lines)
        else:
            activity_str = "No activity"

        embed = discord.Embed(
            title=f"User info - {getattr(target, 'display_name', getattr(target, 'name', str(target)))}",
            color=discord.Color.blurple(),
        )

        try:
            embed.set_thumbnail(url=str(getattr(target, "display_avatar", target.avatar).url))
        except Exception:
            pass

        embed.add_field(name="User ID", value=str(target.id), inline=True)

        created = getattr(target, "created_at", None)
        embed.add_field(name="Account created", value=fmt(created), inline=False)

        if member is not None:
            embed.add_field(name="Server join", value=fmt(getattr(member, "joined_at", None)), inline=False)
            embed.add_field(name="Roles", value=roles_str, inline=False)
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Activity", value=activity_str, inline=False)

        # Send the embed
        try:
            await interaction.response.send_message(embed=embed)
        except Exception:
            logger.exception("Failed to send userinfo for %s", target)
            try:
                await interaction.response.send_message("Failed to fetch user info - check bot permissions or logs.", ephemeral=True)
            except Exception:
                logger.debug("Could not send fallback ephemeral message for userinfo", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserCommandCog(bot))