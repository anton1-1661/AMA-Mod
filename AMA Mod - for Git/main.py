import discord
from discord.ext import commands, tasks
import os
import asyncio
import json
import emoji
import re

intents = discord.Intents.all()  # Alle Intents aktivieren
allowed_mentions = discord.AllowedMentions.none()
allowed_mention = discord.AllowedMentions(users=True)
allowed_channel_ids = [] # Worin Commands ausgeführt werden können
client = commands.Bot(command_prefix=".", intents=intents, allowed_mentions=allowed_mentions)
custom_emote_pattern = re.compile(r"<a?:\w+:\d+>")  # Discord Custom Emotes

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

@client.event
async def on_message(message):
    if message.author.id == client.user.id or message.author.bot:
        return
    
    if message.channel.id == 123456789 or message.channel.id == 123456789: # Vorschläge vzw Bugreports channel worin automatisch nach jeder nachricht threads erstellt werden
        green_check = discord.utils.get(message.guild.emojis, name='check')
        red_cross = discord.utils.get(message.guild.emojis, name='cross')
        thread = await message.channel.create_thread(
            name = f"Vorschlag von {message.author.display_name}",
            message=message,
            auto_archive_duration=10080
        )
        await message.add_reaction(green_check)
        await message.add_reaction(red_cross)
        await thread.send(f"{message.author.mention} hier kannst du mit anderen über deine Idee diskutieren!", allowed_mentions=allowed_mention)

    unicode_emojis = [char for char in message.content if char in emoji.EMOJI_DATA]
    custom_emotes = custom_emote_pattern.findall(message.content)  # Benutzerdefinierte Emotes finden
    total_emotes = len(unicode_emojis) + len(custom_emotes)        # Gesamtanzahl berechnen
    
    if total_emotes >= 6:
        await message.delete()
        await message.channel.send(
            f"{message.author.mention}, **bitte nicht zu viele Emotes senden!**\n_Nur eine Hinweis, keine Verwarnung_",
            delete_after=10, allowed_mentions=allowed_mention)

    if any(link in message.content for link in ['http://', 'https://', 'www.', 'discord.gg/','discord.com/invite/']):
        role = discord.utils.get(message.guild.roles, name="|| Admin")
        linkrole = discord.utils.get(message.guild.roles, id=1305620568615292928)
        if role not in message.author.roles and linkrole not in message.author.roles:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, **bitte keine Links senden!**\n_Nur eine Hinweis, keine Verwarnung_", delete_after=10, allowed_mentions=allowed_mention)
                    
        # Muster für verbotene Links
        forbidden_links = ['discord.gg/', 'discord.com/invite/', 'youtube.com/channel', 'youtube.com/@']
            
        # Benutzer mit der `linkrole`: nur Discord-Server- und YouTube-Kanal-Links verbieten
        if linkrole in message.author.roles and role not in message.author.roles:
            if any(link in message.content for link in forbidden_links):
                await message.delete()
                await message.channel.send(f"{message.author.mention}, **bitte keine Youtubekanal- oder Discordserver-links senden!**\n_Nur eine Hinweis, keine Verwarnung_", delete_after=10, allowed_mentions=allowed_mention)
                return
            
    await client.process_commands(message)

@client.command()
async def rule(ctx):
    await ctx.send(ruletext)
    await ctx.message.delete()

@tasks.loop(hours=48)
async def rule():
    channel = client.get_channel() # Chat Channel worin alle 48 Stunden auf die Regeln hingewiesen wird
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
    await ctx.send(f"Hallo, {ctx.author.mention}!", allowed_mentions=allowed_mention)

@client.tree.command(name="credits", description="Dieser command zeigt die Credits vom Bot")
async def credits(interaction: discord.Interaction): 
    await interaction.response.send_message("Dieser Bot wird **programmiert** von **@anton1_1661** \nDiscord Server: https://www.discord.gg/a3KGf4rpJ6", ephemeral=True)

@client.tree.command(name="help", description="Hier ist noch wenig los.")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(f"<#1283041444558405633>", ephemeral=True)

async def Load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await client.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with client:
        await Load()
        await client.start(token)

asyncio.run(main())