import discord
from discord.ext import commands
import json
import datetime
import pytz

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
    async def ping(self, ctx):
        await ctx.send("Pong!")

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
            self.data[guild_id][member_id] = []

        # Get the current time in Berlin timezone
        berlin_tz = pytz.timezone('Europe/Berlin')
        berlin_time = datetime.datetime.now(berlin_tz)
        timestamp = berlin_time.strftime("%d. %B %Y, %H:%M:%S")

        # Add a new warning with a timestamp
        self.data[guild_id][member_id].append({
            "reason": reason,
            "moderator": str(ctx.author),
            "timestamp": timestamp
        })

        # Save the updated data
        self.save_data()

        await ctx.send(f"{member.mention} wurde **gewarnt** von {ctx.author.mention} \n\n**Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def unwarn(self, ctx, member: discord.Member):
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            if len(self.data[guild_id][member_id]) > 0:
                self.data[guild_id][member_id].pop()
                self.save_data()
                await ctx.send(f"**1** Verwarnung wurde von {member.mention} von **entfernt** \n\n**Teammitglied**: {ctx.author.mention}")
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
            self.data[guild_id][member_id] = []
            self.save_data()
            await ctx.send(f"**Alle** Verwarnungen wurden von {member.mention} **entfernt** \n\n**Teammitglied**: {ctx.author.mention}")
        else:
            await ctx.send(f"{member.mention} hat **keine Verwarnungen**")

    @commands.command(aliases=["warns", "warnings"])
    async def findwarn(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        guild_id = str(ctx.guild.id)
        member_id = str(member.id)

        if guild_id in self.data and member_id in self.data[guild_id]:
            warnings = self.data[guild_id][member_id]

            if warnings:
                warn_messages = []

                for warn in warnings:
                    timestamp = warn["timestamp"]
                    reason = warn["reason"]
                    moderator_name = warn["moderator"]

                    # Versuch, den Moderator anhand des gespeicherten Namens zu finden
                    moderator = None
                    try:
                        # Versuche, den Moderator anhand des gespeicherten Namen und Discriminator zu finden
                        name = warn["moderator"]
                        moderator = discord.utils.get(ctx.guild.members, name=name)
                    except Exception as e:
                        print(f"Fehler beim Finden des Moderators: {e}")

                    # Fallback auf den Namen als Text, wenn der Moderator nicht gefunden wird
                    moderator_mention = moderator.mention if moderator else moderator_name

                    warn_messages.append(f"**-** Am {timestamp}, **Grund**: {reason}, **Teammitglied**: {moderator_mention}")

                warn_message_str = "\n".join(warn_messages)
                await ctx.send(f"**Verwarnungen von {member.mention}:**\n\n{warn_message_str}")
            else:
                await ctx.send(f"**Verwarnungen von {member.mention}:**\n\n_Dieser User hat keine Verwarnungen._")
        else:
            await ctx.send(f"**Verwarnungen von {member.mention}:**\n\n_Dieser User hat keine Verwarnungen._")

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
        await ctx.send(f"**{member.mention}** wurde **gebannt** von **{ctx.message.author.mention}**! \n\n**Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Head_Moderator", "|| Admin", "|| Verified")
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if reason is None:
            reason = "None"
        await member.kick(reason=reason)
        await ctx.send(f"**{member.mention}** wurde **gekickt** von **{ctx.message.author.mention}**! \n\n**Grund:** {reason}")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def mute(self, ctx, member: discord.Member, timelimit):
        try:
            # Ermitteln der Zeiteinheit und des Zeitwerts
            if timelimit.endswith("s"):
                time_unit = "seconds"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("m"):
                time_unit = "minutes"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("h"):
                time_unit = "hours"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("d"):
                time_unit = "days"
                time_value = int(timelimit[:-1])
            elif timelimit.endswith("w"):
                time_unit = "weeks"
                time_value = int(timelimit[:-1])
            else:
                await ctx.reply("Bitte eine gültige Zeiteinheit angeben (s, m, h, d, w).")
                return

            # Überprüfung der maximalen Zeit
            max_times = {
                "seconds": 2419200,  # 28 Tage in Sekunden
                "minutes": 40320,    # 28 Tage in Minuten
                "hours": 672,        # 28 Tage in Stunden
                "days": 28,          # 28 Tage
                "weeks": 4           # 4 Wochen
            }

            if time_value > max_times[time_unit]:
                await ctx.send("Du kannst einen User **max. 28 Tage muten**!")
                return

            # Berechnung der Zeitspanne
            time_delta = datetime.timedelta(**{time_unit: time_value})

            # Mute den Benutzer für die berechnete Zeitspanne
            await member.edit(timed_out_until=discord.utils.utcnow() + time_delta)
            await ctx.send(f"**{member.mention}** wurde **gemutet** von **{ctx.message.author.mention}**! \n\n**Zeit**: {time_value} {time_unit}")

        except Exception as e:
            await ctx.send(f"Es gab einen Fehler beim Muten des Users: {str(e)}")

    @commands.command()
    @commands.has_any_role("|| Moderator", "|| Head_Moderator", "|| Admin", "|| Verified")
    async def unmute(self, ctx, member: discord.Member):
        await member.edit(timed_out_until=None)
        await ctx.send(f"**{member.mention}** wurde **unmutet**! \n\n**Teammitglied**: {ctx.message.author.mention}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
