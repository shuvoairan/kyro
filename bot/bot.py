from __future__ import annotations

import logging
from pathlib import Path

from discord import Intents, Object
from discord.ext import commands

from .config import Settings
from .logging_config import configure_logging

from .db import Database


logger = logging.getLogger(__name__)

COGS_PATH = Path(__file__).parent / "cogs"

DEFAULT_COG_PACKAGES = ["mods", "user"]


class MyBot(commands.Bot):
    def __init__(
        self,
        *,
        intents: Intents,
        command_prefix: str = "!",
        **kwargs,
    ) -> None:
        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            **kwargs,
        )

    db: Database | None = None
    settings: Settings

    async def setup_hook(self) -> None:
        # open DB connection before loading cogs
        settings = self.settings
        db_path = settings.database_path or "data/bot.db"
        self.db = Database(db_path)
        await self.db.connect()
        await self.db.bootstrap()

        # Load cogs from bot/cogs/*.py
        if COGS_PATH.is_dir():
            for file in sorted(COGS_PATH.glob("*.py")):
                if file.name == "__init__.py":
                    continue

                module_path = f"bot.cogs.{file.stem}"
                try:
                    await self.load_extension(module_path)
                    logger.info("Loaded extension %s", module_path)
                except Exception:
                    logger.exception("Failed to load extension %s", module_path)

        # -------- Load selected cog subpackages (e.g. bot/cogs/mods/*.py) ----------
        cog_packages = getattr(settings, "cog_packages", None) or DEFAULT_COG_PACKAGES
        if not isinstance(cog_packages, (list, tuple)):
            logger.warning("cog_packages setting is not iterable; ignoring")
            cog_packages = []

        for pkg in cog_packages:
            pkg_dir = COGS_PATH / pkg
            if not pkg_dir.is_dir():
                logger.debug("Cog package %s not found at %s — skipping", pkg, pkg_dir)
                continue

            # Load all .py files inside package (except __init__.py)
            for file in sorted(pkg_dir.glob("*.py")):
                if file.name == "__init__.py":
                    continue

                module_path = f"bot.cogs.{pkg}.{file.stem}"
                try:
                    await self.load_extension(module_path)
                    logger.info("Loaded extension %s", module_path)
                except Exception:
                    logger.exception("Failed to load extension %s", module_path)

        # Sync commands
        if settings.guild_id:
            guild = Object(id=settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced commands to guild %s", settings.guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced global commands")

    async def close(self) -> None:
        try:
            if self.db:
                await self.db.close()
        finally:
            await super().close()

    async def on_ready(self) -> None:
        logger.info("%s is online (id=%s)", self.user, self.user.id)


def create_bot(settings: Settings | None = None) -> MyBot:
    if settings is None:
        settings = Settings()
    configure_logging(settings.debug)

    intents = Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    intents.members = True
    intents.presences = True

    bot = MyBot(intents=intents)
    bot.settings = settings
    return bot


def run_bot(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    if not settings.token:
        raise RuntimeError("TOKEN is not set in environment (.env)")

    bot = create_bot(settings=settings)
    try:
        bot.run(settings.token)
    except Exception:
        logging.exception("Bot terminated with exception")
        raise
