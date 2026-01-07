from discord import Interaction, app_commands
from discord.ext import commands


class Ping(commands.Cog):
    """Small example cog to verify bot is responsive."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="latency", description="Show gateway latency")
    async def latency(self, interaction: Interaction) -> None:
        await interaction.response.send_message(
            f"Latency: {self.bot.latency * 1000:.0f}ms"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))
