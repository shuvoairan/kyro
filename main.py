import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    case_insensitive=True,
)


@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync: {e}")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="Hi!")
    )


async def load_cogs():
    if not os.path.isdir("./cogs"):
        print("⚠️ No cogs directory found")
        return

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Loaded: {filename}")
            except Exception as e:
                print(f"❌ Failed to load {filename}: {e}")


@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)

    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**Latency:** {latency} ms",
        color=discord.Color.green() if latency < 100 else discord.Color.orange(),
    )

    await ctx.send(embed=embed)


async def main():
    await load_cogs()
    await bot.start(os.getenv("TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
