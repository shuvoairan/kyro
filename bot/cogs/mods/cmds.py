from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import View, button, Button

from bot.services.mod_logging import log_moderation_action

logger = logging.getLogger(__name__)

class ConfirmKickView(View):
    def __init__(
        self,
        *,
        invoker: discord.User,
        target_member: discord.Member,
        reason: Optional[str],
        bot: commands.Bot,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.invoker = invoker
        self.target_member = target_member
        self.reason = reason
        self.bot = bot
        self.result: Optional[dict] = None  # filled after confirm/cancel

    async def _disable_all(self, interaction: Optional[Interaction] = None) -> None:
        # Disable all buttons and attempt to edit the original response to reflect disabled UI
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True
        if interaction is not None:
            try:
                # edit original response
                await interaction.edit_original_response(view=self)
            except Exception:
                logger.debug("Failed to edit original response while disabling UI", exc_info=True)

    @button(label="Confirm kick", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button_: Button) -> None:
        # only allow the invoker to confirm
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the user who invoked the command can confirm this action.",
                ephemeral=True,
            )
            return

        # Prevent double-press by disabling UI immediately and editing message
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Performing kick…", view=self)
        moderator = interaction.user
        target = self.target_member
        reason = self.reason or "No reason provided"
        ts = int(datetime.utcnow().timestamp())

        # Attempt kick - let discord.py raise the correct exceptions and handle them explicitly
        success = False
        kick_note = None
        try:
            await target.kick(reason=f"{reason} - moderator:{moderator} ({moderator.id})")
            success = True
        except discord.Forbidden:
            success = False
            kick_note = "Missing permissions or role hierarchy prevents kick (Forbidden)."
            logger.warning("Kick forbidden: moderator=%s target=%s", moderator, target)
        except discord.NotFound:
            success = False
            kick_note = "Member not found / already left the guild."
            logger.info("Kick attempted but member not found: %s", target)
        except discord.HTTPException as exc:
            success = False
            kick_note = f"Discord API error during kick: {exc!r}"
            logger.exception("HTTPException while kicking %s", target)
        except Exception as exc:
            success = False
            kick_note = f"Unexpected error during kick: {exc!r}"
            logger.exception("Unexpected error while kicking %s", target)

        try:
            modlog_result = await log_moderation_action(
                self.bot,
                action="kick",
                target_id=target.id,
                target_name=str(target),
                moderator_id=moderator.id,
                moderator_name=str(moderator),
                reason=reason,
                success=success,
                note=kick_note,
                timestamp=ts,
            )
        except Exception as exc:
            # If the logging helper itself fails, record that for the moderator message
            logger.exception("log_moderation_action failed unexpectedly")
            modlog_result = None

        # Build final message to moderator (ephemeral)
        parts = []
        if success:
            parts.append(f"✅ Successfully kicked {target.mention}")
        else:
            parts.append(f"❌ Failed to kick {target} - see log for details")

        if kick_note:
            parts.append(f"Kick: {kick_note} - Please report this to a developer")

        final_content = "\n".join(parts)

        # send follow-up ephemeral to the moderator
        try:
            await interaction.followup.send(final_content, ephemeral=True)
        except Exception:
            # fallback: try to edit original response
            try:
                await interaction.edit_original_response(content=final_content, view=self)
            except Exception:
                logger.debug("Failed to send followup or edit original response for kick confirmation", exc_info=True)

        # disable UI permanently
        await self._disable_all(interaction)

    @button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button_: Button) -> None:
        # This should not normally occur because the interaction is ephemeral,
        # but we still guard against unexpected interaction states or client behavior.
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the user who invoked the command can cancel this action.",
                ephemeral=True,
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Kick cancelled.", view=self)
        await self._disable_all(interaction)


class ConfirmBanView(View):
    def __init__(
        self,
        *,
        invoker: discord.User,
        target_member: discord.Member,
        reason: Optional[str],
        bot: commands.Bot,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.invoker = invoker
        self.target_member = target_member
        self.reason = reason
        self.bot = bot
        self.result: Optional[dict] = None  # filled after confirm/cancel

    async def _disable_all(self, interaction: Optional[Interaction] = None) -> None:
        # Disable all buttons and attempt to edit the original response to reflect disabled UI
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True
        if interaction is not None:
            try:
                # edit original response
                await interaction.edit_original_response(view=self)
            except Exception:
                logger.debug("Failed to edit original response while disabling UI", exc_info=True)

    @button(label="Confirm ban", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button_: Button) -> None:
        # only allow the invoker to confirm
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the user who invoked the command can confirm this action.",
                ephemeral=True,
            )
            return

        # Prevent double-press by disabling UI immediately and editing message
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Performing ban…", view=self)
        moderator = interaction.user
        target = self.target_member
        reason = self.reason or "No reason provided"
        ts = int(datetime.utcnow().timestamp())

        # Attempt kick - let discord.py raise the correct exceptions and handle them explicitly
        success = False
        ban_note = None
        try:
            await target.ban(reason=f"{reason} - moderator:{moderator} ({moderator.id})")
            success = True
        except discord.Forbidden:
            success = False
            ban_note = "Missing permissions or role hierarchy prevents ban (Forbidden)."
            logger.warning("Ban forbidden: moderator=%s target=%s", moderator, target)
        except discord.NotFound:
            success = False
            ban_note = "Member not found / already left the guild."
            logger.info("Ban attempted but member not found: %s", target)
        except discord.HTTPException as exc:
            success = False
            ban_note = f"Discord API error during ban: {exc!r}"
            logger.exception("HTTPException while kicking %s", target)
        except Exception as exc:
            success = False
            ban_note = f"Unexpected error during ban: {exc!r}"
            logger.exception("Unexpected error while kicking %s", target)

        try:
            modlog_result = await log_moderation_action(
                self.bot,
                action="ban",
                target_id=target.id,
                target_name=str(target),
                moderator_id=moderator.id,
                moderator_name=str(moderator),
                reason=reason,
                success=success,
                note=ban_note,
                timestamp=ts,
            )
        except Exception as exc:
            logger.exception("log_moderation_action failed for ban")
            modlog_result = None

        # Build final message to moderator (ephemeral)
        parts = []
        if success:
            parts.append(f"✅ Successfully banned {target.mention}")
        else:
            parts.append(f"❌ Failed to banned {target} - see log for details")

        if ban_note:
            parts.append(f"Kick: {ban_note} - Please report this to a developer")

        final_content = "\n".join(parts)

        # send follow-up ephemeral to the moderator
        try:
            await interaction.followup.send(final_content, ephemeral=True)
        except Exception:
            # fallback: try to edit original response
            try:
                await interaction.edit_original_response(content=final_content, view=self)
            except Exception:
                logger.debug("Failed to send followup or edit original response for kick confirmation", exc_info=True)

        # disable UI permanently
        await self._disable_all(interaction)

    @button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button_: Button) -> None:
        # This should not normally occur because the interaction is ephemeral,
        # but we still guard against unexpected interaction states or client behavior.
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the user who invoked the command can cancel this action.",
                ephemeral=True,
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Ban cancelled.", view=self)
        await self._disable_all(interaction)

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_moderator(self, interaction: Interaction) -> bool:
        # prefer a configured mod role; fallback to guild perm kick_members
        settings = getattr(self.bot, "settings", None)
        mod_role_id = getattr(settings, "mod_role_id", None) if settings else None
        if mod_role_id:
            role = interaction.guild.get_role(mod_role_id)
            return role in interaction.user.roles if role else False
        # fallback
        return interaction.user.guild_permissions.kick_members

    @app_commands.command(
        name="kick",
        description="Kick a member (requires moderator role or Kick Members permission)."
    )
    @app_commands.describe(member="Member to kick", reason="Reason for the kick (optional)")
    async def kick(
        self,
        interaction: Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        # Basic checks
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        if not self._is_moderator(interaction):
            await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
            return

        # Prevent self-kick and bot-kick
        if member.id == interaction.user.id:
            await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
            return
        if member.id == self.bot.user.id:
            await interaction.response.send_message("I cannot kick myself.", ephemeral=True)
            return

        # Role hierarchy check
        try:
            invoker_member = interaction.guild.get_member(interaction.user.id)
            if invoker_member is None:
                invoker_member = await interaction.guild.fetch_member(interaction.user.id)
            # allow guild owner to bypass role ordering checks
            if (
                member.top_role >= invoker_member.top_role
                and interaction.user.id != interaction.guild.owner_id
            ):
                await interaction.response.send_message(
                    "You cannot kick a member with an equal or higher role than you.", ephemeral=True
                )
                return
        except Exception:
            # If role check fails for some reason, continue but log it
            logger.exception("Failed to check role hierarchy while attempting to kick %s", member)

        # Ask for confirmation via button UI (ephemeral)
        view = ConfirmKickView(invoker=interaction.user, target_member=member, reason=reason, bot=self.bot)
        await interaction.response.send_message(
            f"Confirm kicking {member.mention}? This action is irreversible.", view=view, ephemeral=True
        )

    @app_commands.command(
        name="ban",
        description="Ban a member (requires moderator role or Ban Members permission)."
    )
    @app_commands.describe(member="Member to ban", reason="Reason for the ban (optional)")
    async def ban(
        self,
        interaction: Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        # Basic checks
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return


        if not self._is_moderator(interaction):
            await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
            return

        # Prevent self-ban and bot-ban
        if member.id == interaction.user.id:
            await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
            return
        if member.id == self.bot.user.id:
            await interaction.response.send_message("I cannot ban myself.", ephemeral=True)
            return

        # Role hierarchy check
        try:
            invoker_member = interaction.guild.get_member(interaction.user.id)
            if invoker_member is None:
                invoker_member = await interaction.guild.fetch_member(interaction.user.id)
            # allow guild owner to bypass role ordering checks
            if (
                member.top_role >= invoker_member.top_role
                and interaction.user.id != interaction.guild.owner_id
            ):
                await interaction.response.send_message(
                    "You cannot ban a member with an equal or higher role than you.", ephemeral=True
                )
                return
        except Exception:
            # If role check fails for some reason, continue but log it
            logger.exception("Failed to check role hierarchy while attempting to ban %s", member)

        # Ask for confirmation via button UI
        view = ConfirmBanView(invoker=interaction.user, target_member=member, reason=reason, bot=self.bot)
        await interaction.response.send_message(
            f"Confirm banning {member.mention}? This action is irreversible.", view=view, ephemeral=True
        )



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))