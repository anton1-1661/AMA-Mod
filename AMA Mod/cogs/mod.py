import discord
from discord.ext import commands
import json
import datetime

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Load or initialize the data
        try:
            with open("cogs/json/warn.json", "r") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {}
        except json.JSONDecodeError:
            self.data = {}

    def save_data(self):
        with open("cogs/json/warn.json", "w") as f:
            json.dump(self.data, f, indent=4)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Moderation is ready!")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        if reason is None:
            reason = "None"

        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        # Initialize the guild's data if it doesn't exist
        if guild_id not in self.data:
            self.data[guild_id] = {}

        # Initialize the member's data if it doesn't exist
        if member_id not in self.data[guild_id]:
            self.data[guild_id][member_id] = {"Warns": 0}

        # Increment the warn count
        self.data[guild_id][member_id]["Warns"] += 1

        # Save the updated data
        self.save_data()

        await ctx.send(f"{member.mention} wurde **gewarnt** von {ctx.author.mention} **Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def unwarn(self, ctx, member: discord.Member):
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            if self.data[guild_id][member_id]["Warns"] > 0:
                self.data[guild_id][member_id]["Warns"] -= 1
                self.save_data()
                await ctx.send(f"**1** Verwarnung wurde von {member.mention} von {ctx.author.mention} **entfernt**")
            else:
                await ctx.send(f"{member.mention} hat **keine Verwarnungen**")
        else:
            await ctx.send(f"{member.mention} hat **keine Verwarnungen**")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def delwarn(self, ctx, member: discord.Member):
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            self.data[guild_id][member_id]["Warns"] = 0
            self.save_data()
            await ctx.send(f"**Alle** Verwarnungen von {member.mention} wurden von {ctx.author.mention} **entfernt**")
        else:
            await ctx.send(f"{member.mention} hat **keine Verwarnungen**")

    @commands.command(aliases=["warns", "warnings"])
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def findwarn(self, ctx, member: discord.Member):
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            warns = self.data[guild_id][member_id].get("Warns", 0)
            await ctx.send(f"{member.mention} hat {warns} Warn/s")
        else:
            await ctx.send(f"{member.mention} hat **keine Verwarnungen**")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def say(self, ctx, *, message=None):
        await ctx.message.delete()
        await ctx.send(message)

    @commands.command()
    @commands.has_any_role("|| Head_Moderator", "|| Admin", "|| Verified")
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        if reason is None:
            reason = "None"
        await member.ban(reason=reason)
        await ctx.send(f"**{member.mention}** wurde **gebannt** von **{ctx.message.author.mention}**! **Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Head_Moderator", "|| Admin", "|| Verified")
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if reason is None:
            reason = "None"
        await member.kick(reason=reason)
        await ctx.send(f"**{member.mention}** wurde **gekickt** von **{ctx.message.author.mention}**! **Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def mute(self, ctx, member: discord.Member, timelimit):
        if "s" in timelimit:
            gettime = timelimit.strip("s")
            if int(gettime) > 2419000:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
            else:
                newtime = datetime.timedelta(seconds=int(gettime))
                await member.edit(timed_out_until=discord.utils.utcnow() + newtime)
                await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}** für **{newtime}**!")
        if "m" in timelimit:
            gettime = timelimit.strip("m")
            if int(gettime) > 40320:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
            else:
                newtime = datetime.timedelta(minutes=int(gettime))
                await member.edit(timed_out_until=discord.utils.utcnow() + newtime)
                await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}** für **{newtime}**!")
        if "h" in timelimit:
            gettime = timelimit.strip("h")
            if int(gettime) > 672:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
            else:
                newtime = datetime.timedelta(hours=int(gettime))
                await member.edit(timed_out_until=discord.utils.utcnow() + newtime)
                await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}** für **{newtime}**!")
        if "d" in timelimit:
            gettime = timelimit.strip("d")
            if int(gettime) > 28:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
            else:
                newtime = datetime.timedelta(days=int(gettime))
                await member.edit(timed_out_until=discord.utils.utcnow() + newtime)
                await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}** für **{newtime}**!")
        if "w" in timelimit:
            gettime = timelimit.strip("w")
            if int(gettime) > 4:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
            else:
                newtime = datetime.timedelta(weeks=int(gettime))
                await member.edit(timed_out_until=discord.utils.utcnow() + newtime)
                await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}** für **{newtime}**!")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def unmute(self, ctx, member: discord.Member):
        await member.edit(timed_out_until=None)
        await ctx.send(f"**{member.mention}** wurde **unmutet** von **{ctx.message.author.mention}**!")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
