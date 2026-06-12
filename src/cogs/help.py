import discord
from discord import app_commands
from discord.ext import commands
import json
import os


class HelpView(discord.ui.View):
    def __init__(
        self, user_id, transcribe_cmd_id=None, languages_cmd_id=None, help_cmd_id=None
    ):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.current_page = 0
        self.total_pages = 2
        self.message = None
        self.transcribe_cmd_id = transcribe_cmd_id
        self.languages_cmd_id = languages_cmd_id
        self.help_cmd_id = help_cmd_id

        self.update_buttons()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
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

            embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
        else:
            embed = discord.Embed(
                title="Credits",
                description="",
                color=0x7BB2D9,
            )

            embed.add_field(
                name="Authors",
                value="[@dromzeh](https://github.com/dromzeh)",
                inline=False,
            )

            embed.add_field(
                name="Contributions",
                value="[@strazto](https://instagram.com/strazto)",
                inline=False,
            )

            embed.add_field(
                name="Operated By",
                value="Antifield LTD",
                inline=False,
            )

            embed.add_field(
                name="Repository",
                value="[github.com/antifield/vmt](https://github.com/antifield/vmt)",
                inline=False,
            )

            embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")

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
        transcribe_cmd = discord.utils.get(
            await self.bot.tree.fetch_commands(), name="transcribe"
        )
        languages_cmd = discord.utils.get(
            await self.bot.tree.fetch_commands(), name="languages"
        )
        help_cmd = discord.utils.get(await self.bot.tree.fetch_commands(), name="help")

        view = HelpView(
            interaction.user.id,
            transcribe_cmd.id if transcribe_cmd else None,
            languages_cmd.id if languages_cmd else None,
            help_cmd.id if help_cmd else None,
        )
        embed = view.create_embed()
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=not public
        )
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Help(bot))
