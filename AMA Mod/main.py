import discord
from discord.ext import commands, tasks
import os
import asyncio
from itertools import cycle
import datetime
import json

client = commands.Bot(command_prefix=".", intents=discord.Intents.all())

bot_statuses = cycle(["Hallo", "Warum schaust du dir das an?", "Bester Bot ever :)"])

@tasks.loop(seconds=5)
async def change_bot_status():
    await client.change_presence(activity=discord.Game(next(bot_statuses)))

@client.event
async def on_ready():
    await client.tree.sync()
    print("Bot online!")
    change_bot_status.start()

@client.event 
async def on_message(message): 
    if message.author.id == client.user.id or message.author.bot:
        return
    if any(link in message.content for link in ['http://', 'https://', 'www.']): 
        await message.delete()
        await message.channel.send(f"{message.author.mention}, bitte poste keine Links.") 
     
    await client.process_commands(message) 

@client.event
async def on_guild_join(guild):
    with open("cogs/json/warn.json", "r") as f:
        data = json.load(f)

    data[str(guild.id)] = {}

    for member in guild.members:
        data[str(guild.id)][str(member.id)] = {}
        data[str(guild.id)][str(member.id)]["Warns"] = 0

    with open("cogs/json/warn.json", "w"):
        json.dump(data, f, indent=4)

@client.event
async def on_guild_remove(guild):
    with open("cogs/json/warn.json", "r") as f:
        data = json.load(f)

    data.pop(str(guild.id))

    with open("cogs/json/warn.json", "w"):
        json.dump(data, f, indent=4)

@client.command(aliases=["hallo", "moin"])
async def hello(ctx):
    await ctx.send(f"Hallo, {ctx.author.mention}!")

@client.command()
async def stinky(ctx, member: discord.Member=None):
    if member is None:
        member = ctx.author
    await ctx.send(f"{member.mention}, du stinkst!")

@client.command()
@commands.has_any_role("|| Verified", "|| Admin")
async def dumm(ctx):
    dumm_satzlen = f"Anzahl Zeichen **{len(dumm_satz)} -4**"
    dumm_satz = "Du bist **DUMM**"
    await ctx.send(dumm_satz)

@client.tree.command(name="credits", description="Dieser command zeigt die Credits vom Bot")
async def credits(interaction: discord.Interaction): 
    await interaction.response.send_message(f"Dieser Bot wurde **programmiert** von **@anton1_1661** \nDiscord Server: https://www.discord.gg/a3KGf4rpJ6")

@client.command()
@commands.has_any_role("|| Verified", "|| Admin")
async def sendembed(ctx):
    embeded_msg = discord.Embed(title="Titel vom embed", description="Beschreibeung vom embed", color=discord.Color.blue())
    embeded_msg.set_thumbnail(url=ctx.guild.icon)
    embeded_msg.add_field(name="Name vom Feld", value="Inhalt vom Feld", inline=False)
    embeded_msg.set_footer(text="Autor unten", icon_url=ctx.author.avatar)
    embeded_msg.set_author(name="Autor oben", icon_url=ctx.author.avatar)
    await ctx.send(embed=embeded_msg)

@client.tree.command(name="help", description="Alle Commands im Bot")
async def help(interaction: discord.Interaction): #Hallo hier ist Anton SUS !

    await interaction.response.send_message(f"Hallo hier ist noch wenig los!")

with open("token.txt") as file:
    token = file.read()

async def Load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await client.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with client:
        await Load()
        await client.start(token)

asyncio.run(main())