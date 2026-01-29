from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import discord
import re
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import View, button, Button

from bot.services.mod_logging import log_moderation_action

logger = logging.getLogger(__name__)

def parse_user_id(value: str) -> int:
    if value is None:
        raise ValueError("no value provided")

    s = str(value).strip()
    m = re.search(r"(\d{5,25})", s)
    if not m:
        raise ValueError(f"could not parse an ID from: {value!r}")
    try:
        uid = int(m.group(1))
    except Exception as exc:
        raise ValueError("parsed ID is not a valid integer") from exc

    if uid <= 0:
        raise ValueError("parsed ID is not positive")
    if uid > 10 ** 30:
        raise ValueError("parsed ID looks invalid (too large)")

    return uid

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

        # Attempt ban - let discord.py raise the correct exceptions and handle them explicitly
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

class ConfirmUnbanView(View):
    def __init__(
        self,
        *,
        invoker: discord.User,
        target_user_id: int,
        reason: Optional[str],
        bot: commands.Bot,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.invoker = invoker
        self.target_user_id = int(target_user_id)
        self.reason = reason
        self.bot = bot

    async def _disable_all(self, interaction: Optional[Interaction] = None) -> None:
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True
        if interaction is not None:
            try:
                await interaction.edit_original_response(view=self)
            except Exception:
                logger.debug("Failed to edit original response while disabling UI (unban)", exc_info=True)

    @button(label="Confirm unban", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction: Interaction, button_: Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the user who invoked the command can confirm this action.",
                ephemeral=True,
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Performing unban…", view=self)

        moderator = interaction.user
        user_id = int(self.target_user_id)
        reason = self.reason or "No reason provided"
        ts = int(datetime.utcnow().timestamp())
        guild = interaction.guild

        target_name = f"User {user_id}"
        try:
            fetched_user = await self.bot.fetch_user(user_id)
            target_name = f"{fetched_user} ({user_id})"
        except Exception:
            logger.debug("Could not fetch user %s for nicer display", user_id, exc_info=True)

        success = False
        unban_note: Optional[str] = None
        ban_check_error: Optional[str] = None
        ban_entry = None

        try:
            try:
                ban_entry = await guild.fetch_ban(discord.Object(id=user_id))
            except TypeError:
                bans = await guild.bans()
                found = None
                for b in bans:
                    cand = getattr(b, "user", None)
                    if cand is None:
                        try:
                            cand_id = int(b)
                        except Exception:
                            continue
                    else:
                        cand_id = getattr(cand, "id", None)
                        if cand_id is None:
                            try:
                                cand_id = int(cand)
                            except Exception:
                                continue
                    if cand_id == user_id:
                        found = b
                        break
                ban_entry = found
            except discord.NotFound:
                ban_entry = None
        except discord.Forbidden:
            ban_entry = None
            ban_check_error = "Missing permission to read ban list (Forbidden)."
            logger.warning("fetch_ban forbidden: guild=%s moderator=%s", getattr(guild, "id", None), moderator)
        except Exception as exc:
            ban_entry = None
            ban_check_error = f"Error checking ban status: {exc!r}"
            logger.exception("Error while checking ban status for %s", user_id)

        if ban_entry is None and ban_check_error is None:
            success = False
            unban_note = "User is not banned."
            logger.info("Unban attempted for user not banned: %s", user_id)
        else:
            try:
                await guild.unban(discord.Object(id=user_id), reason=f"{reason} - moderator:{moderator} ({moderator.id})")
                success = True
            except discord.Forbidden:
                success = False
                unban_note = "Missing permissions to unban (Forbidden)."
                logger.warning("Unban forbidden: moderator=%s target=%s", moderator, user_id)
            except discord.NotFound:
                success = False
                unban_note = "User not found in ban list (maybe already unbanned)."
                logger.info("Unban: NotFound for %s", user_id)
            except discord.HTTPException as exc:
                success = False
                unban_note = f"Discord API error during unban: {exc!r}"
                logger.exception("HTTPException while unbanning %s", user_id)
            except Exception as exc:
                success = False
                unban_note = f"Unexpected error during unban: {exc!r}"
                logger.exception("Unexpected error while unbanning %s", user_id)

        notes = []
        if ban_check_error:
            notes.append(f"Ban-check: {ban_check_error}")
        if unban_note:
            notes.append(f"Unban: {unban_note}")
        action_note = "; ".join(notes) if notes else None

        try:
            await log_moderation_action(
                self.bot,
                action="unban",
                target_id=user_id,
                target_name=target_name,
                moderator_id=moderator.id,
                moderator_name=str(moderator),
                reason=reason,
                success=success,
                note=action_note,
                timestamp=ts,
            )
        except Exception:
            logger.exception("log_moderation_action failed for unban")

        parts = []
        if success:
            parts.append(f"✅ Successfully unbanned {target_name}")
        else:
            parts.append(f"❌ Failed to unban {target_name} - see log for details")
        if action_note:
            parts.append(action_note)

        final_content = "\n".join(parts)

        try:
            await interaction.followup.send(final_content, ephemeral=True)
        except Exception:
            try:
                await interaction.edit_original_response(content=final_content, view=self)
            except Exception:
                logger.debug("Failed to send followup or edit original response for unban confirmation", exc_info=True)

        await self._disable_all(interaction)

    @button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button_: Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the user who invoked the command can cancel this action.",
                ephemeral=True,
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Unban cancelled.", view=self)
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

    @app_commands.command(
        name="unban",
        description="Unban a user by user ID or mention (requires moderator role or Ban Members permission)."
    )
    @app_commands.describe(user_id="User ID or mention to unban (e.g. 123456789012345678 or <@123...>)", reason="Reason for the unban (optional)")
    async def unban(
        self,
        interaction: Interaction,
        user_id: str,
        reason: Optional[str] = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        try:
            uid = parse_user_id(user_id)
        except ValueError:
            await interaction.response.send_message(
                "Please provide a valid user ID or mention (e.g. `123456789012345678` or `<@123...>`).",
                ephemeral=True,
            )
            return

        if not self._is_moderator(interaction):
            await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)
            return

        # Prevent nonsense self/unban bot checks
        if uid == interaction.user.id:
            await interaction.response.send_message("You cannot unban yourself.", ephemeral=True)
            return
        if uid == self.bot.user.id:
            await interaction.response.send_message("I cannot unban myself.", ephemeral=True)
            return

        view = ConfirmUnbanView(invoker=interaction.user, target_user_id=uid, reason=reason, bot=self.bot)
        await interaction.response.send_message(
            f"Confirm unbanning user id `{uid}`? This action is irreversible.", view=view, ephemeral=True
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))