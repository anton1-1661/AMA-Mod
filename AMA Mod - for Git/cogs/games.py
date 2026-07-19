import discord
from discord.ext import commands
import aiohttp
import json
from random import choice
import asyncpraw as praw
import os

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reddit = praw.Reddit(client_id="", client_secret="", user_agent="")
        self.channel_id = 123456789  # Deine Zählchannel-ID
        self.data_file = "cogs\json\counting_data.json"
        self.current_number = 1
        self.last_user_id = None
        self.allowed_channel_ids = [1253032508082229340, 1002302289626804244]

        # Lade die gespeicherten Daten, wenn die Datei existiert
        self.load_data()

    def load_data(self):
        """Lädt die gespeicherten Zähldaten aus der Datei."""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.current_number = data.get("current_number", 1)
                self.last_user_id = data.get("last_user_id", None)

    def save_data(self):
        """Speichert die Zähldaten in einer Datei."""
        data = {
            "current_number": self.current_number,
            "last_user_id": self.last_user_id
        }
        with open(self.data_file, 'w') as f:
            json.dump(data, f)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Games is ready!")

    @commands.command(aliases=["randommeme"])
    async def meme(self, ctx: commands.Context):
        # Überprüfen, ob der Befehl in einem der erlaubten Channels verwendet wird
        if ctx.channel.id not in self.allowed_channel_ids:
            await ctx.send(f"{ctx.author.mention} bitte führe diesem Befehl nur in <#1253032508082229340> aus.", delete_after=10)
            return

        subreddit = await self.reddit.subreddit("memes")
        posts_lists = []

        async for post in subreddit.hot(limit=30):
            if not post.over_18 and post.author is not None and any(post.url.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif"]):
                author_name = post.author.name
                posts_lists.append((post.url, author_name))
            if post.author is None:
                posts_lists.append((post.url, "N/A"))

        if posts_lists:
            random_post = choice(posts_lists)
            meme_embed = discord.Embed(title="Random Meme", description="Random Meme von r/memes", color=discord.Color.random())
            meme_embed.set_author(name=f"Meme wurde angefragt von {ctx.author.name}", icon_url=ctx.author.avatar)
            meme_embed.set_image(url=random_post[0])
            meme_embed.set_footer(text=f"Post erstellt von {random_post[1]}", icon_url=None)
            await ctx.send(embed=meme_embed)
        else:
            await ctx.send("Fehler 303, bitte versuche es später nochmal.")

    def cog_unload(self):
        self.bot.loop.create_task(self.reddit.close())

    @commands.command(aliases=["chatgpt"])
    @commands.has_permissions(administrator=True)
    async def gpt(self, ctx: commands.Context, *, prompt: str):
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "davinci-002",
                "prompt": prompt,
                "temperature": 0.5,
                "max_tokens": 50,
                "presence_penalty": 0,
                "frequency_penalty": 0,
                "best_of": 1,
            }
            with open("cogs/json/config.json", "r") as f:
                config = json.load(f)
                api_key = config["api_key"]

            headers = {"Authorization": f"Bearer {api_key}"}
            try:
                async with session.post("https://api.openai.com/v1/completions", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        response = await resp.json()
                        gpt_text = response["choices"][0]["text"].strip()
                        gpt_embed = discord.Embed(title="ChatGPT's Antwort:", description=gpt_text)
                        await ctx.reply(embed=gpt_embed)
                    else:
                        error_message = await resp.text()
                        await ctx.reply(f"Fehler bei der Anfrage: {error_message}")
            except Exception as e:
                await ctx.reply(f"Es gab einen Fehler bei der Anfrage: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id != self.channel_id:
            return

        # Hier holen wir uns den Channel
        channel = self.bot.get_channel(self.channel_id)

        try:
            number = int(message.content)
        except ValueError:
            return  # Wenn die Nachricht keine Zahl ist, ignorieren

        if message.author.id == self.last_user_id:
            # Wenn derselbe User wieder eine Zahl sendet, lösche die Nachricht
            await message.delete()
            await channel.send(f"{message.author.mention}, du musst dich mit anderen **abwechseln**!")
            return

        if number == self.current_number:
            await message.add_reaction('✅')  # Grüner Haken für richtige Zahl
            self.current_number += 1
            self.last_user_id = message.author.id
            self.save_data()  # Speichere die neue Zahl und den Benutzer
        else:
            await message.add_reaction('❌')  # Rotes X für falsche Zahl
            await message.channel.send(f'**Verloren!** \n\nWir starten bei **1**.')
            self.current_number = 1
            self.last_user_id = None
            self.save_data()  # Setze die Daten auf Anfang zurück und speichere

async def setup(bot):
    await bot.add_cog(Games(bot))