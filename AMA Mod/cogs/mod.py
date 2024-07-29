import discord
from discord.ext import commands, tasks
import datetime
import json


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Moderation is ready!")

    @commands.command()
    async def say(self, ctx, *,message=None):
        await ctx.send(message)

    @commands.command()
    @commands.has_any_role("|| Head_Moderator", "|| Admin", "|| Verfied")
    async def ban(self, ctx, member:discord.Member, *, reason = None):
        if reason == None:
            reason = "None"
        await member.ban(reason=reason)
        await ctx.send(f"**{member.mention}** wurde **gebannt** von **{ctx.message.author.mention}**! **Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Head_Moderator", "|| Admin", "|| Verfied")
    async def kick(self, ctx, member:discord.Member, *, reason = None):
        if reason == None:
            reason = "None"
        await member.kick(reason=reason)
        await ctx.send(f"**{member.mention}** wurde **gekickt** von **{ctx.message.author.mention}**! **Grund:** {reason}")
        

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verfied")
    async def mute(self, ctx, member:discord.Member, timelimit):
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
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verfied")
    async def unmute(self, ctx, member:discord.Member):
        await member.edit(timed_out_until=None)
        await ctx.send(f"**{member.mention}** wurde **unmutet** von **{ctx.message.author.mention}**!")

async def setup(bot):
    await bot.add_cog(Moderation(bot))