import discord
from discord.ext import commands, tasks
import json
import time

class LevelSys(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_activity.start()

        self.level_roles = {
            10: "Lvl 10",
            20: "Lvl 20",
            30: "Lvl 30",
            40: "Lvl 40",
            50: "Lvl 50",
            60: "Lvl 60",
            70: "Lvl 70",
            80: "Lvl 80",
            90: "Lvl 90",
            100: "Lvl 100",
        }

    def get_xp_for_level(self, level):
        if level < 0:
            return 0
        return 100 * level

    def get_next_level_xp(self, level):
        return self.get_xp_for_level(level + 1)

    async def save_data(self, data):
        with open("cogs/json/users.json", "w") as f:
            json.dump(data, f, indent=4)

    @commands.Cog.listener()
    async def on_ready(self):
        print("LevelSys is ready!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id or message.author.bot:
            return

        user_id = str(message.author.id)
        guild_id = str(message.guild.id)

        try:
            with open("cogs/json/users.json", "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except json.JSONDecodeError:
            data = {}

        if guild_id not in data:
            data[guild_id] = {}

        if user_id not in data[guild_id]:
            data[guild_id][user_id] = {"level": 0, "xp": 0, "last_xp_time": 0}

        current_time = int(time.time())
        last_xp_time = data[guild_id][user_id].get("last_xp_time", 0)
        if current_time - last_xp_time >= 30:
            user_data = data[guild_id][user_id]
            user_data["xp"] += 3
            user_data["last_xp_time"] = current_time

            current_level = user_data["level"]
            current_xp = user_data["xp"]

            if current_level < 100:
                next_level_xp = self.get_next_level_xp(current_level + 1) - current_xp

                if current_xp >= self.get_xp_for_level(current_level + 1):
                    user_data["level"] += 1
                    user_data["xp"] -= self.get_xp_for_level(current_level + 1)

                    if user_data["level"] > 100:
                        user_data["level"] = 100
                        user_data["xp"] = 0

                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        role_name = self.level_roles.get(user_data["level"])
                        if role_name:
                            role = discord.utils.get(guild.roles, name=role_name)
                            if role:
                                member = guild.get_member(int(user_id))
                                if member:
                                    await member.add_roles(role)
                                    # Send a DM to the user, but no ping
                                    try:
                                        await member.send(f"Herzlichen Glückwunsch! Du hast Level {user_data['level']} erreicht und die Rolle '{role_name}' erhalten.")
                                    except discord.Forbidden:
                                        pass  # Handle the case where DM fails

            await self.save_data(data)

    @tasks.loop(seconds=30)
    async def voice_activity(self):
        for guild in self.bot.guilds:
            try:
                with open("cogs/json/users.json", "r") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {}
            except json.JSONDecodeError:
                data = {}

            if str(guild.id) not in data:
                data[str(guild.id)] = {}

            for member in guild.members:
                if member.voice and member.voice.channel:
                    user_id = str(member.id)
                    if user_id not in data[str(guild.id)]:
                        data[str(guild.id)][user_id] = {"level": 0, "xp": 0, "last_xp_time": 0}

                    user_data = data[str(guild.id)][user_id]
                    current_time = int(time.time())
                    user_data["xp"] += 2  # 2 XP alle 30 Sekunden

                    current_level = user_data["level"]
                    current_xp = user_data["xp"]

                    if current_level < 100:
                        next_level_xp = self.get_next_level_xp(current_level + 1) - current_xp

                        if current_xp >= self.get_xp_for_level(current_level + 1):
                            user_data["level"] += 1
                            user_data["xp"] -= self.get_xp_for_level(current_level + 1)

                            if user_data["level"] > 100:
                                user_data["level"] = 100
                                user_data["xp"] = 0

                            role_name = self.level_roles.get(user_data["level"])
                            if role_name:
                                role = discord.utils.get(guild.roles, name=role_name)
                                if role:
                                    await member.add_roles(role)
                                    # Send a DM to the user, but no ping
                                    try:
                                        await member.send(f"Herzlichen Glückwunsch! Du hast Level {user_data['level']} erreicht und die Rolle '{role_name}' erhalten.")
                                    except discord.Forbidden:
                                        pass  # Handle the case where DM fails

            await self.save_data(data)

    @commands.command(aliases=["rank"])
    async def level(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        user_id = str(member.id)
        guild_id = str(ctx.guild.id)

        try:
            with open("cogs/json/users.json", "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except json.JSONDecodeError:
            data = {}

        if guild_id not in data or user_id not in data[guild_id]:
            await ctx.send(f"`@{member.name}#{member.discriminator}` hat noch kein Level erreicht.")
            return

        user_data = data[guild_id][user_id]
        level = user_data["level"]
        xp = user_data["xp"]

        next_level_xp = self.get_next_level_xp(level) - xp
        total_xp = self.get_xp_for_level(level) + xp

        all_xps = [user["xp"] + self.get_xp_for_level(user["level"]) for user in data[guild_id].values()]
        all_xps.sort(reverse=True)
        rank = all_xps.index(total_xp) + 1

        xp_for_next_rank = 0
        if rank > 1:
            xp_for_next_rank = all_xps[rank - 2] - total_xp

        if rank > 1:
            await ctx.send(f"{member.mention} ist aktuell **Level {level}** ({xp} XP) und damit auf **Rang {rank}**. \nBis zum **nächsten Level** braucht {member.mention} noch {next_level_xp} XP. \nBis zum **nächsten Rang** braucht {member.mention} noch {xp_for_next_rank} XP.")
        elif rank == 1:
            await ctx.send(f"{member.mention} ist aktuell **Level {level}** ({xp} XP) und damit auf **Rang {rank}**. \nBis zum **nächsten Level** braucht {member.mention} noch {next_level_xp} XP.")

    @commands.command(aliases=["lb"])
    async def leaderboard(self, ctx):
        guild_id = str(ctx.guild.id)

        try:
            with open("cogs/json/users.json", "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except json.JSONDecodeError:
            data = {}

        if guild_id not in data:
            await ctx.send("Es gibt keine Level-Daten für diese Gilde.")
            return

        leaderboard = sorted(data[guild_id].items(), key=lambda x: (self.get_xp_for_level(x[1]["level"]) + x[1]["xp"]), reverse=True)
        top_users = leaderboard[:10]

        leaderboard_text = "Leaderboard\n"
        for idx, (user_id, user_data) in enumerate(top_users, start=1):
            user = await self.bot.fetch_user(int(user_id))
            leaderboard_text += f"{idx}. {user.mention} - Level {user_data['level']} ({user_data['xp']} XP)\n"

        await ctx.send(leaderboard_text)

async def setup(bot):
    await bot.add_cog(LevelSys(bot))
