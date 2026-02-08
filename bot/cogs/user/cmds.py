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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserCommandCog(bot))