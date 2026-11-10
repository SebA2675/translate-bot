import os
import json
import sqlite3
import discord
from discord import app_commands

TOKEN = os.environ["DISCORD_TOKEN"]
DB_PATH = "bot.db"

# (code, name, flag), 25 languages = the max for one dropdown
LANGUAGES = [
    ("en", "English", "🇬🇧"),
    ("es", "Español", "🇪🇸"),
    ("pt", "Português", "🇧🇷"),
    ("fr", "Français", "🇫🇷"),
    ("de", "Deutsch", "🇩🇪"),
    ("it", "Italiano", "🇮🇹"),
    ("nl", "Nederlands", "🇳🇱"),
    ("pl", "Polski", "🇵🇱"),
    ("ru", "Русский", "🇷🇺"),
    ("uk", "Українська", "🇺🇦"),
    ("tr", "Türkçe", "🇹🇷"),
    ("ar", "العربية", "🇸🇦"),
    ("fa", "فارسی", "🇮🇷"),
    ("hi", "हिन्दी", "🇮🇳"),
    ("bn", "বাংলা", "🇧🇩"),
    ("ur", "اردو", "🇵🇰"),
    ("id", "Bahasa Indonesia", "🇮🇩"),
    ("vi", "Tiếng Việt", "🇻🇳"),
    ("th", "ไทย", "🇹🇭"),
    ("fil", "Filipino", "🇵🇭"),
    ("zh-CN", "中文 (简体)", "🇨🇳"),
    ("zh-TW", "中文 (繁體)", "🇹🇼"),
    ("ja", "日本語", "🇯🇵"),
    ("ko", "한국어", "🇰🇷"),
    ("ro", "Română", "🇷🇴"),
]
ALL_CODES = [code for code, _, _ in LANGUAGES]
LANG_BY_CODE = {code: (name, flag) for code, name, flag in LANGUAGES}


# ---------- tiny database helper ----------
def run_db(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(sql, params)
        con.commit()
        return cur.fetchall()
    finally:
        con.close()


def init_db():
    run_db(
        "CREATE TABLE IF NOT EXISTS announcements ("
        "message_id INTEGER PRIMARY KEY, text TEXT NOT NULL, languages TEXT NOT NULL)"
    )


# ---------- translation (FAKE for now) ----------
async def translate(text, target_code):
    # TEMPORARY: we will replace this with the real translator later.
    return f"(test translation to {target_code})\n\n{text}"


# ---------- the dropdown under each announcement ----------
class LanguageSelect(discord.ui.Select):
    def __init__(self, codes=None):
        codes = codes or ALL_CODES
        options = [
            discord.SelectOption(label=LANG_BY_CODE[c][0], value=c, emoji=LANG_BY_CODE[c][1])
            for c in codes
        ]
        super().__init__(
            custom_id="tr:pick",
            placeholder="🌐 Translate this announcement…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        code = self.values[0]
        rows = run_db(
            "SELECT text, languages FROM announcements WHERE message_id = ?",
            (interaction.message.id,),
        )
        if not rows:
            await interaction.response.send_message(
                "Sorry, I can't find this announcement anymore.", ephemeral=True
            )
            return
        text, langs_json = rows[0]
        # reset the dropdown so the same language can be picked again
        await interaction.response.edit_message(view=TranslateView(json.loads(langs_json)))
        translated = await translate(text, code)
        name, flag = LANG_BY_CODE[code]
        await interaction.followup.send(f"{flag} **{name}**\n\n{translated}", ephemeral=True)


class TranslateView(discord.ui.View):
    def __init__(self, codes=None):
        super().__init__(timeout=None)
        self.add_item(LanguageSelect(codes))


# ---------- /send: modal -> language picker -> post ----------
class PickLanguagesView(discord.ui.View):
    def __init__(self, channel, text):
        super().__init__(timeout=300)
        self.channel = channel
        self.text = text
        self.chosen = []

    @discord.ui.select(
        placeholder="Languages to offer (leave empty = all 25)",
        min_values=0,
        max_values=25,
        options=[
            discord.SelectOption(label=name, value=code, emoji=flag)
            for code, name, flag in LANGUAGES
        ],
    )
    async def pick(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.chosen = list(select.values)
        await interaction.response.defer()

    @discord.ui.button(label="Post announcement", style=discord.ButtonStyle.success)
    async def post(self, interaction: discord.Interaction, button: discord.ui.Button):
        codes = self.chosen or ALL_CODES
        try:
            msg = await self.channel.send(content=self.text, view=TranslateView(codes))
        except discord.Forbidden:
            await interaction.response.edit_message(
                content="I can't post in that channel. Please check my permissions there.",
                view=None,
            )
            return
        run_db(
            "INSERT OR REPLACE INTO announcements (message_id, text, languages) VALUES (?, ?, ?)",
            (msg.id, self.text, json.dumps(codes)),
        )
        await interaction.response.edit_message(
            content=f"✅ Posted in {self.channel.mention}", view=None
        )


class AnnouncementModal(discord.ui.Modal, title="New announcement"):
    message = discord.ui.TextInput(
        label="Announcement",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        placeholder="Type your announcement here…",
    )

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        view = PickLanguagesView(self.channel, self.message.value)
        await interaction.response.send_message(
            "Choose which languages to offer (leave empty for all), then press **Post announcement**.",
            view=view,
            ephemeral=True,
        )


# ---------- the bot ----------
class TranslateBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        init_db()
        self.add_view(TranslateView())  # keeps old dropdowns working after restarts
        await self.tree.sync()


bot = TranslateBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓", ephemeral=True)


@bot.tree.command(name="send", description="Post an announcement with a translation menu")
@app_commands.describe(channel="Where to post the announcement")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def send(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.send_modal(AnnouncementModal(channel))


bot.run(TOKEN)
