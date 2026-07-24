import json
import os

import discord
from discord import app_commands
from discord.ext import commands


def format_duration(seconds: float) -> str:
    # seconds, then minutes, then hours, whichever reads naturally
    if seconds < 90:
        return f"{seconds:.0f} sec"
    if seconds < 7200:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


class HelpView(discord.ui.View):
    def __init__(
        self,
        user,
        transcribe_cmd_id=None,
        languages_cmd_id=None,
        help_cmd_id=None,
        stats=None,
    ):
        super().__init__(timeout=60)
        self.user = user
        self.user_id = user.id
        self.current_page = 0
        self.total_pages = 2
        self.message: discord.Message | None = None
        self.transcribe_cmd_id = transcribe_cmd_id
        self.languages_cmd_id = languages_cmd_id
        self.help_cmd_id = help_cmd_id
        self.stats = stats or {}

        self.update_buttons()

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

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def create_embed(self):
        if self.current_page == 0:
            embed = discord.Embed(
                title="vmt Help",
                description="Transcribe + Translate Discord Voice Messages",
                color=0x7BB2D9,
            )

            embed.add_field(
                name="How to Use",
                value="**1.** Right-click/hold down on any Voice Message\n**2.** Navigate to **Apps > Select Voice Message**\n**3.** Use </transcribe:{}>\n**4.** Provide a language to translate into (optional)".format(
                    self.transcribe_cmd_id if self.transcribe_cmd_id else "0"
                ),
                inline=False,
            )

            embed.add_field(
                name="Commands",
                value="</transcribe:{}> Transcribe selected voice message\n</languages:{}> View available languages\n</help:{}> Show this menu".format(
                    self.transcribe_cmd_id if self.transcribe_cmd_id else "0",
                    self.languages_cmd_id if self.languages_cmd_id else "0",
                    self.help_cmd_id if self.help_cmd_id else "0",
                ),
                inline=False,
            )

        else:
            ping_ms = self.stats.get("ping_ms")
            started_ts = self.stats.get("started_ts")

            lines = [
                "Created by [dromzeh](https://dromzeh.dev) · [antifield/vmt](https://github.com/antifield/vmt)",
                "",
                f"**Ping** {ping_ms}ms" if ping_ms is not None else "**Ping** ...",
                f"**Online** since <t:{started_ts}:R>"
                if started_ts
                else "**Online** just now",
                # transcribed totals hidden 4 now
                # f"**Transcribed** {self.stats.get('clips', 0):,} clips"
                # f" · {format_duration(self.stats.get('seconds', 0.0))}",
            ]

            embed = discord.Embed(
                title="About vmt",
                description="\n".join(lines),
                color=0x7BB2D9,
            )

        embed.set_footer(
            text=f"Requested by {self.user.name} • Page {self.current_page + 1}/{self.total_pages}",
            icon_url=self.user.display_avatar.url,
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your menu!", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.blurple)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.blurple)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()

    def load_config(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "config.json"
        )
        with open(config_path) as conf_file:
            return json.load(conf_file)

    @app_commands.command(
        name="help", description="Show all available commands and features"
    )
    @app_commands.describe(public="Should everyone see this response? (default: false)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def help(self, interaction: discord.Interaction, public: bool = False):
        # one fetch for all three command ids instead of three round trips
        cmds = await self.bot.tree.fetch_commands()
        transcribe_cmd = discord.utils.get(cmds, name="transcribe")
        languages_cmd = discord.utils.get(cmds, name="languages")
        help_cmd = discord.utils.get(cmds, name="help")

        clips, seconds = await self.bot.usage.totals()
        started_at = getattr(self.bot, "started_at", None)
        stats = {
            "ping_ms": round(self.bot.latency * 1000),
            "started_ts": int(started_at.timestamp()) if started_at else None,
            "clips": clips,
            "seconds": seconds,
        }

        view = HelpView(
            interaction.user,
            transcribe_cmd.id if transcribe_cmd else None,
            languages_cmd.id if languages_cmd else None,
            help_cmd.id if help_cmd else None,
            stats=stats,
        )
        embed = view.create_embed()
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=not public
        )
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Help(bot))
