from discord.ext import commands


class Test(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Test cog has loaded!")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.reply("Pong!", mention_author=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Test(bot))
