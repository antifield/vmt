import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from vmt.cache import checksum_of
from vmt.services.transcription import EmptyTranscriptionError

log = logging.getLogger(__name__)

SELECTED_MESSAGE_TTL_SECS = 15 * 60

# discord caps embed field values at 1024 chars, anything longer gets the paged layout
EMBED_FIELD_LIMIT = 1024

# 3800 because the description cap is 4096 and we prepend a bold label, plus
# title + footer have to fit in discord's 6000 total embed cap. this leaves
# comfortable headroom on both
PAGE_CHAR_LIMIT = 3800


def split_into_pages(text: str, limit: int = PAGE_CHAR_LIMIT) -> list[str]:
    text = text.strip() if text else ""
    if not text:
        return [""]

    pages = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            pages.append(remaining)
            break

        # look one char past the limit so a word ending exactly at the limit still fits
        window = remaining[: limit + 1]
        cut = -1
        for i, ch in enumerate(window):
            if ch.isspace():
                cut = i

        if cut <= 0:
            # one giant word with nowhere to break, hard split it
            pages.append(remaining[:limit])
            remaining = remaining[limit:].lstrip()
        else:
            pages.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()

    return pages


def fits_in_fields(transcribed_text: str, translated_text: str | None = None) -> bool:
    # short messages keep the classic stacked-fields embed, long ones get paged
    if len(transcribed_text or "") > EMBED_FIELD_LIMIT:
        return False
    if translated_text is not None and len(translated_text) > EMBED_FIELD_LIMIT:
        return False
    return True


class TranscriptView(discord.ui.View):
    def __init__(
        self,
        transcribed_text,
        author,
        ctx_author,
        translate_to=None,
        translated_text=None,
    ):
        super().__init__(timeout=180)
        self.author = author
        self.ctx_author = ctx_author
        self.translate_to = translate_to
        self.message: discord.Message | None = None
        self.current_page = 0
        self.active = "transcription"

        self.pages = {"transcription": split_into_pages(transcribed_text)}
        if translate_to and translated_text:
            self.pages["translation"] = split_into_pages(str(translated_text))

        self.view_select = None
        if translate_to and "translation" in self.pages:
            self.view_select = discord.ui.Select(
                options=[
                    discord.SelectOption(
                        label="Transcription", value="transcription", default=True
                    ),
                    discord.SelectOption(
                        label=f"Translation ({translate_to.upper()})",
                        value="translation",
                    ),
                ],
                row=1,
            )
            self.view_select.callback = self.switch_view
            self.add_item(self.view_select)

        self.update_components()

    async def on_timeout(self):
        for item in self.children:
            # only buttons and selects have a disabled switch
            if isinstance(item, discord.ui.Button | discord.ui.Select):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    def update_components(self):
        pages = self.pages[self.active]
        if len(pages) > 1:
            if self.previous_button not in self.children:
                self.add_item(self.previous_button)
                self.add_item(self.next_button)
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= len(pages) - 1
        else:
            # single page, no point showing pager buttons
            self.remove_item(self.previous_button)
            self.remove_item(self.next_button)

    def create_embed(self):
        pages = self.pages[self.active]
        if self.active == "translation" and self.translate_to:
            label = f"**Translation (Into {self.translate_to.upper()})**"
        else:
            label = "**Transcription**"

        embed = discord.Embed(
            color=0xACD8AA,
            title=f"{self.author.name}'s Voice Message",
            description=f"{label}\n\n{pages[self.current_page]}",
        )

        footer = f"Requested by {self.ctx_author.name}"
        if len(pages) > 1:
            footer += f" • Page {self.current_page + 1}/{len(pages)}"
        embed.set_footer(text=footer, icon_url=self.ctx_author.display_avatar.url)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx_author.id:
            await interaction.response.send_message(
                "This isn't your menu!", ephemeral=True
            )
            return False
        return True

    async def switch_view(self, interaction: discord.Interaction):
        if self.view_select is None:
            return
        self.active = self.view_select.values[0]
        self.current_page = 0
        for option in self.view_select.options:
            option.default = option.value == self.active
        self.update_components()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.blurple, row=0)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page -= 1
        self.update_components()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.blurple, row=0)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page += 1
        self.update_components()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


def next_utc_midnight_timestamp() -> int:
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(midnight.timestamp())


class Transcriber(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.max_duration = bot.settings.max_voice_message_duration

        # who picked which message and when, so we can forget stale picks later
        self.selected_messages: dict[int, tuple[discord.Message, float]] = {}

        # command id for clickable </transcribe:id> mentions, fetched once on first use
        self._transcribe_cmd_id: int | None = None

        self.select_menu = app_commands.ContextMenu(
            name="Select Voice Message",
            callback=self.select_voice_message,
        )
        self.select_menu.allowed_installs = app_commands.AppInstallationType(
            guild=True, user=True
        )
        self.select_menu.allowed_contexts = app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        self.bot.tree.add_command(self.select_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.select_menu.name, type=self.select_menu.type)

    def load_config(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "config.json"
        )
        with open(config_path) as conf_file:
            return json.load(conf_file)

    async def _transcribe_mention(self) -> str:
        # clickable command mention when we can get the id, plain text otherwise
        if self._transcribe_cmd_id is None:
            try:
                cmds = await self.bot.tree.fetch_commands()
                cmd = discord.utils.get(cmds, name="transcribe")
                if cmd:
                    self._transcribe_cmd_id = cmd.id
            except discord.HTTPException:
                log.warning("could not fetch command id for /transcribe mention")
        if self._transcribe_cmd_id is None:
            return "/transcribe"
        return f"</transcribe:{self._transcribe_cmd_id}>"

    def _purge_expired_selections(self):
        cutoff = time.monotonic() - SELECTED_MESSAGE_TTL_SECS
        expired = [
            user_id
            for user_id, (_, selected_at) in self.selected_messages.items()
            if selected_at < cutoff
        ]
        for user_id in expired:
            del self.selected_messages[user_id]

    async def select_voice_message(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        self._purge_expired_selections()

        if not msg_has_voice_note(message):
            await interaction.response.send_message(
                "This message does not contain a voice message.", ephemeral=True
            )
            return

        attachment = message.attachments[0]
        duration = attachment.duration
        if duration and duration > self.max_duration:
            await interaction.response.send_message(
                f"Voice message is too long. Maximum duration is {self.max_duration} seconds. This voice message is {int(duration)} seconds.",
                ephemeral=True,
            )
            return

        self.selected_messages[interaction.user.id] = (message, time.monotonic())
        mention = await self._transcribe_mention()
        await interaction.response.send_message(
            f"Voice message selected! Use {mention} to transcribe it.", ephemeral=True
        )

    async def language_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        language_codes = self.config["language_codes"]

        popular_languages = [
            "EN-US",
            "ES",
            "FR",
            "DE",
            "JA",
            "ZH",
            "PT-BR",
            "RU",
            "IT",
            "NL",
        ]

        if not current:
            choices = [
                app_commands.Choice(name=f"{code} - {language_codes[code]}", value=code)
                for code in popular_languages
                if code in language_codes
            ]
            return choices[:25]

        current_upper = current.upper()
        current_lower = current.lower()

        exact_matches = []
        code_matches = []
        name_matches = []

        for code, name in language_codes.items():
            if code == current_upper:
                exact_matches.append((code, name))
            elif code.startswith(current_upper):
                code_matches.append((code, name))
            elif current_lower in name.lower():
                name_matches.append((code, name))

        all_matches = exact_matches + code_matches + name_matches
        choices = [
            app_commands.Choice(name=f"{code} - {name}", value=code)
            for code, name in all_matches
        ]

        return choices[:25]

    @app_commands.command(
        name="transcribe", description="Transcribe the selected voice message"
    )
    @app_commands.describe(
        translate_to="Language code to translate to (e.g., EN-US, ES, FR)",
        public="Should everyone see this response? (default: false)",
    )
    @app_commands.autocomplete(translate_to=language_autocomplete)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def transcribe(
        self,
        interaction: discord.Interaction,
        translate_to: str | None = None,
        public: bool = False,
    ):
        self._purge_expired_selections()

        if interaction.user.id not in self.selected_messages:
            await interaction.response.send_message(
                "No voice message selected! Right-click a message and select 'Select Voice Message' first.",
                ephemeral=True,
            )
            return

        message, _ = self.selected_messages[interaction.user.id]
        await self._transcribe_message(interaction, message, translate_to, public)

    async def _transcribe_message(
        self,
        interaction: discord.Interaction,
        message: discord.Message,
        translate_to: str | None = None,
        public: bool = False,
    ):
        await interaction.response.defer(ephemeral=not public)

        if translate_to is not None:
            translate_to = translate_to.upper()
            language_codes = self.config["language_codes"]
            if translate_to not in language_codes:
                valid_codes = ", ".join([f"`{code}`" for code in language_codes])
                await interaction.followup.send(
                    f"**Invalid language code.**\n> Valid language codes: {valid_codes}",
                    ephemeral=True,
                )
                return

        if not msg_has_voice_note(message):
            await interaction.followup.send(
                "This message does not contain a voice message.", ephemeral=True
            )
            return

        author = message.author
        attachment = message.attachments[0]
        duration = attachment.duration or 0.0

        try:
            audio_bytes = await attachment.read()
            checksum = checksum_of(audio_bytes)

            cached = await self.bot.cache.get_transcript(checksum)
            from_cache = cached is not None

            if from_cache:
                transcribed_text, _provider = cached
            else:
                allowed, seconds_remaining = await self.bot.usage.check_quota(
                    interaction.user.id, duration
                )
                if not allowed:
                    log.info(
                        "Quota denied for user %s (%.0fs left, clip is %.0fs)",
                        interaction.user.id,
                        seconds_remaining or 0.0,
                        duration,
                    )
                    await interaction.followup.send(
                        self._quota_message(seconds_remaining), ephemeral=True
                    )
                    return

                transcribed_text = await self.bot.provider.transcribe(audio_bytes)
                await self.bot.cache.store_transcript(
                    checksum, transcribed_text, self.bot.provider.name, duration
                )
                await self.bot.usage.record_usage(interaction.user.id, duration)

            translated_text = None
            if translate_to is not None and transcribed_text:
                translated_text = await self.bot.cache.get_translation(
                    checksum, translate_to
                )
                if translated_text is None:
                    try:
                        translated_text = await self.bot.translator.translate(
                            transcribed_text, translate_to
                        )
                        await self.bot.cache.store_translation(
                            checksum, translate_to, translated_text
                        )
                    except Exception:
                        log.exception("Translation error")
                        translated_text = None

            # only count the translation if it will actually be shown
            shown_translation = (
                str(translated_text) if translate_to and translated_text else None
            )

            if fits_in_fields(transcribed_text, shown_translation):
                embed = make_embed(
                    transcribed_text,
                    author,
                    interaction.user,
                    translate_to,
                    translated_text,
                )
                await interaction.followup.send(embed=embed, ephemeral=not public)
            else:
                view = TranscriptView(
                    transcribed_text,
                    author,
                    interaction.user,
                    translate_to if shown_translation else None,
                    shown_translation,
                )
                view.message = await interaction.followup.send(
                    embed=view.create_embed(), view=view, ephemeral=not public
                )

        except EmptyTranscriptionError:
            await interaction.followup.send(
                f"Could not transcribe the Voice Message from {author} as the response was empty.",
                ephemeral=True,
            )
        except Exception:
            await interaction.followup.send(
                f"Could not transcribe the Voice Message from {author} due to an error.",
                ephemeral=True,
            )
            log.exception("Transcription error")

    def _quota_message(self, seconds_remaining: float | None) -> str:
        limit = self.bot.usage.daily_limit_seconds
        remaining = seconds_remaining or 0.0
        used = max(limit - remaining, 0.0)
        reset_ts = next_utc_midnight_timestamp()
        return (
            f"**Daily limit reached.** You've used {used / 60:.1f} of "
            f"{limit / 60:.1f} minutes today ({remaining / 60:.1f} minutes "
            f"remaining). Your limit resets <t:{reset_ts}:R>."
        )


def make_embed(
    transcribed_text,
    author,
    ctx_author=None,
    translate_to=None,
    translated_text=None,
):
    embed = discord.Embed(
        color=0xACD8AA,
        title=f"{author.name}'s Voice Message",
    )
    embed.add_field(
        name="Transcription",
        value=transcribed_text,
        inline=False,
    )

    if translate_to and translated_text:
        embed.add_field(
            name=f"Translation (Into {translate_to.upper()})",
            value=str(translated_text),
            inline=False,
        )

    if ctx_author:
        embed.set_footer(
            text=f"Requested by {ctx_author.name}",
            icon_url=ctx_author.display_avatar.url,
        )

    return embed


def msg_has_voice_note(msg: discord.Message | None) -> bool:
    if not msg:
        return False
    if not msg.attachments or not msg.flags.voice:
        return False
    return True


async def setup(bot):
    await bot.add_cog(Transcriber(bot))
