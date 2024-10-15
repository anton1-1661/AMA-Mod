import discord
from discord.ext import commands, tasks
import os
import asyncio
from itertools import cycle
import datetime
import json

intents = discord.Intents.all()  # Alle Intents aktivieren
allowed_mentions = discord.AllowedMentions.none()
allowed_channel_ids = [1253032238703181946, 1002302289626804244]
client = commands.Bot(command_prefix=".", intents=intents, allowed_mentions=allowed_mentions)

@client.event
async def on_ready():
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="AMA YouTube"))
    await client.tree.sync()
    rule.start()
    print("Bot online!")

with open("cogs/json/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
    no_permission_message = config["no_permission_message"]
    ruletext = config["ruletext"]
    token = config["token"]

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(no_permission_message)
    else:
        await ctx.send("Ein **Fehler** ist aufgetreten!")

@client.event
async def on_message(message):
    if message.author.id == client.user.id or message.author.bot:
        return

    if any(link in message.content for link in ['http://', 'https://', 'www.']):
        role = discord.utils.get(message.guild.roles, name="|| Admin")
        if role not in message.author.roles:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, bitte poste keine Links.")

    if message.channel.id == 1234567890123456789 or message.channel.id == 1234567890123456789: # Channel id durch Vorschläge Channel ersetzen
        green_check = discord.utils.get(message.guild.emojis, name='check')
        red_cross = discord.utils.get(message.guild.emojis, name='cross')
        thread = await message.channel.create_thread(
            name = f"Vorschlag von {message.author.display_name}",
            message=message,
            auto_archive_duration=10080
        )
        await message.add_reaction(green_check)
        await message.add_reaction(red_cross)
        await thread.send(f"{message.author.mention} hier kannst du mit anderen über deine Idee diskutieren!")

    await client.process_commands(message)

@client.command()
async def rule(ctx):
    await ctx.send(ruletext)
    await ctx.message.delete()

@tasks.loop(hours=48)
async def rule():
    channel = client.get_channel(1002266257103540289)
    await channel.send(ruletext)

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
    # Überprüfen, ob der Befehl in einem der erlaubten Channels verwendet wird
    if ctx.channel.id not in allowed_channel_ids:
        return

    if member is None:
        member = ctx.author
    await ctx.send(f"{member.mention}, du stinkst!")

@client.tree.command(name="credits", description="Dieser command zeigt die Credits vom Bot")
async def credits(interaction: discord.Interaction): 
    await interaction.response.send_message("Dieser Bot wird **programmiert** von **@anton1_1661** \nDiscord Server: https://www.discord.gg/a3KGf4rpJ6",)

@client.command()
@commands.has_permissions(administrator=True)
async def sendembed(ctx):
    embeded_msg = discord.Embed(title="Titel vom embed", description="Beschreibeung vom embed", color=discord.Color.blue())
    embeded_msg.set_thumbnail(url=ctx.guild.icon)
    embeded_msg.add_field(name="Name vom Feld", value="Inhalt vom Feld", inline=False)
    embeded_msg.set_footer(text="Autor unten", icon_url=ctx.author.avatar)
    embeded_msg.set_author(name="Autor oben", icon_url=ctx.author.avatar)
    await ctx.send(embed=embeded_msg)

@client.tree.command(name="help", description="Hier ist noch wenig los.")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(f"<#1253032238703181946>")

async def Load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await client.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with client:
        await Load()
        await client.start(token) # Macht etwas 

asyncio.run(main())
