import os
import discord
from discord import app_commands

TOKEN = os.environ["DISCORD_TOKEN"]


class TranslateBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = TranslateBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓", ephemeral=True)


bot.run(TOKEN)
