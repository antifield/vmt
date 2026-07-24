import json
import os

import discord
from discord import app_commands
from discord.ext import commands


class LanguageView(discord.ui.View):
    def __init__(self, language_codes, user, transcribe_cmd_id=None):
        super().__init__(timeout=60)
        self.language_codes = language_codes
        self.user = user
        self.user_id = user.id
        self.current_page = 0
        self.items_per_page = 18
        self.message: discord.Message | None = None
        self.transcribe_cmd_id = transcribe_cmd_id

        sorted_codes = sorted(language_codes.items(), key=lambda x: x[1])
        self.pages = [
            sorted_codes[i : i + self.items_per_page]
            for i in range(0, len(sorted_codes), self.items_per_page)
        ]
        self.total_pages = len(self.pages)

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

    def create_embed(self, transcribe_cmd_id=None):
        description = (
            "Use these codes with </transcribe:{}>"
            if transcribe_cmd_id
            else "Use these codes with /transcribe"
        )

        embed = discord.Embed(
            title="Translation Languages",
            description=(
                description.format(transcribe_cmd_id)
                if transcribe_cmd_id
                else description
            ),
            color=0x7BB2D9,
        )

        page_languages = self.pages[self.current_page]

        language_list = "\n".join(
            [f"**{name}** • {code}" for code, name in page_languages]
        )

        embed.add_field(
            name="",
            value=language_list,
            inline=False,
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
        await interaction.response.edit_message(
            embed=self.create_embed(self.transcribe_cmd_id), view=self
        )

    @discord.ui.button(label="▶", style=discord.ButtonStyle.blurple)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.create_embed(self.transcribe_cmd_id), view=self
        )


class OtherCommands(commands.Cog):
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
        name="languages",
        description="List all available language codes for translation",
    )
    @app_commands.describe(public="Should everyone see this response? (default: false)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def languages(self, interaction: discord.Interaction, public: bool = False):
        transcribe_cmd = discord.utils.get(
            await self.bot.tree.fetch_commands(), name="transcribe"
        )
        transcribe_cmd_id = transcribe_cmd.id if transcribe_cmd else None

        view = LanguageView(
            self.config["language_codes"], interaction.user, transcribe_cmd_id
        )
        embed = view.create_embed(transcribe_cmd_id)
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=not public
        )
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(OtherCommands(bot))
