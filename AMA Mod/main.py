import discord
from discord.ext import commands, tasks
import os
import asyncio
from itertools import cycle
import datetime

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())

bot_statuses = cycle(["Hallo", "Warum schaust du dir das an?", "Bester Bot ever :)"])

@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(next(bot_statuses)))

@bot.event
async def on_ready():
    print("Bot online!")
    change_bot_status.start()

@bot.command(aliases=["hallo", "moin"])
async def hello(ctx):
    await ctx.send(f"Hallo, {ctx.author.mention}!")

@bot.command()
async def mihail(ctx):
    await ctx.send(f"{ctx.author.mention}, du stinkst!")

@bot.command()
@commands.has_any_role("|| Verified")
async def mihail1(ctx, member: discord.Member):
    await ctx.send(f"{member.mention}, du stinkst!")

@bot.command()
@commands.has_any_role("|| Verified")
async def lukas(ctx):
    lukas = "Lukas ist **DUMM**"
    for a in range(1):
        await ctx.send(lukas)
    lukaslen = f"Anzahl Zeichen **{len(lukas)}**"
    await ctx.send(lukaslen)

@bot.command()
@commands.has_any_role("|| Verified")
async def mama(ctx):
    await ctx.send("Hallo")

@bot.command()
@commands.has_any_role("|| Verified", "|| Admin")
async def sendembed(ctx):
    embeded_msg = discord.Embed(title="Titel vom embed", description="Beschreibeung vom embed", color=discord.Color.blue())
    embeded_msg.set_thumbnail(url=ctx.guild.icon)
    embeded_msg.add_field(name="Name vom Feld", value="Inhalt vom Feld", inline=False)
    embeded_msg.set_footer(text="Autor unten", icon_url=ctx.author.avatar)
    embeded_msg.set_author(name="Autor oben", icon_url=ctx.author.avatar)
    await ctx.send(embed=embeded_msg)

with open("token.txt") as file:
    token = file.read()

async def Load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with bot:
        await Load()
        await bot.start(token)

asyncio.run(main())