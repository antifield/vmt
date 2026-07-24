import logging
import os
import sys

import discord
from discord.ext import commands

from vmt.cache import Cache
from vmt.db import Database
from vmt.services.transcription import get_provider
from vmt.services.translation import Translator
from vmt.settings import Settings, SettingsError, load_settings
from vmt.usage import UsageTracker

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self, settings: Settings):
        # what discord events we're allowed to see
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.settings = settings
        self.db = Database(
            path=settings.db_path,
            sync_url=settings.turso_database_url,
            auth_token=settings.turso_auth_token,
        )
        self.provider = get_provider(settings)
        self.translator = Translator(
            settings.deepl_api_key, use_free_api=settings.deepl_free_api
        )
        self.usage = UsageTracker(self.db, settings.daily_limit_seconds)
        self.cache = Cache(self.db)

    async def setup_hook(self) -> None:
        await self.db.connect()
        if self.usage.unlimited:
            log.info("DAILY_LIMIT_SECONDS not set, quotas disabled")
        else:
            log.info(
                "Daily quota: %.0f seconds per user", self.settings.daily_limit_seconds
            )

        cogs_loaded = 0
        cogs_count = 0
        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
        for cog_file in os.listdir(cogs_path):
            if cog_file.endswith(".py") and cog_file != "__init__.py":
                cogs_count += 1
                try:
                    log.info("Loading cog %s...", cog_file)
                    await self.load_extension(f"vmt.cogs.{cog_file[:-3]}")
                    cogs_loaded += 1
                except Exception:
                    log.exception("Failed to load cog %s", cog_file)
        log.info("Loaded %d/%d cogs.", cogs_loaded, cogs_count)

        await self.tree.sync()
        log.info("Slash commands synced!")

    async def on_ready(self):
        # remember first ready for the /help uptime stat, reconnects don't reset it
        if getattr(self, "started_at", None) is None:
            self.started_at = discord.utils.utcnow()
        if self.user:
            log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        log.info("vmt is ready to transcribe and translate voice messages!")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    try:
        settings = load_settings()
    except SettingsError as exc:
        log.error("%s", exc)
        return 1

    bot = Bot(settings)
    bot.run(settings.bot_token, log_handler=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
