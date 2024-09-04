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
        """Berechnet die XP-Anforderungen für das angegebene Level."""
        if level < 1:
            return 0
        return 50 * level

    def get_total_xp_for_level(self, level):
        """Berechnet die gesamte XP, die benötigt wird, um das angegebene Level zu erreichen."""
        return sum(self.get_xp_for_level(i) for i in range(1, level + 1))

    def get_next_level_xp(self, level):
        """Berechnet die XP, die für das nächste Level benötigt wird."""
        return self.get_xp_for_level(level + 1)

    async def save_data(self, data):
        """Speichert die Daten in einer JSON-Datei."""
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
            data[guild_id][user_id] = {"level": 0, "xp": 0, "total_xp": 0, "last_xp_time": 0}

        user_data = data[guild_id][user_id]
        current_time = int(time.time())
        last_xp_time = user_data.get("last_xp_time", 0)
        
        if current_time - last_xp_time >= 30:
            user_data["xp"] += 3
            user_data["last_xp_time"] = current_time

            current_level = user_data["level"]
            current_xp = user_data["xp"]

            total_xp = self.get_total_xp_for_level(current_level) + current_xp

            if current_level < 100:
                if total_xp >= self.get_total_xp_for_level(current_level + 1):
                    user_data["level"] += 1
                    user_data["xp"] = total_xp - self.get_total_xp_for_level(user_data["level"])

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
                                    try:
                                        await member.send(f"Herzlichen Glückwunsch! Du hast Level {user_data['level']} erreicht und die Rolle '{role_name}' erhalten.")
                                    except discord.Forbidden:
                                        pass  # Handle the case where DM fails

            user_data["total_xp"] = self.get_total_xp_for_level(user_data["level"]) + user_data["xp"]
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
                        data[str(guild.id)][user_id] = {"level": 0, "xp": 0, "total_xp": 0, "last_xp_time": 0}

                    user_data = data[str(guild.id)][user_id]
                    current_time = int(time.time())
                    user_data["xp"] += 5  # 5 XP alle 30 Sekunden

                    current_level = user_data["level"]
                    current_xp = user_data["xp"]

                    total_xp = self.get_total_xp_for_level(current_level) + current_xp

                    if current_level < 100:
                        if total_xp >= self.get_total_xp_for_level(current_level + 1):
                            user_data["level"] += 1
                            user_data["xp"] = total_xp - self.get_total_xp_for_level(user_data["level"])

                            if user_data["level"] > 100:
                                user_data["level"] = 100
                                user_data["xp"] = 0

                            role_name = self.level_roles.get(user_data["level"])
                            if role_name:
                                role = discord.utils.get(guild.roles, name=role_name)
                                if role:
                                    await member.add_roles(role)
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
            await ctx.send(f"{member.mention} hat noch kein Level erreicht.")
            return

        user_data = data[guild_id][user_id]
        level = user_data["level"]
        xp = user_data["xp"]
        total_xp = user_data["total_xp"]

        next_level_xp = self.get_next_level_xp(level) - xp

        # Rang berechnen
        all_xps = [user["total_xp"] for user in data[guild_id].values()]
        all_xps.sort(reverse=True)
        rank = all_xps.index(total_xp) + 1

        xp_for_next_rank = 0
        if rank > 1:
            xp_for_next_rank = all_xps[rank - 2] - total_xp

        if rank > 1:
            await ctx.send(f"{member.mention} ist aktuell **Level {level}** ({total_xp} XP) und damit auf **Rang {rank}**. \nBis zum **nächsten Level** braucht {member.mention} noch {next_level_xp} XP. \nBis zum **nächsten Rang** braucht {member.mention} noch {xp_for_next_rank} XP.")
        else:
            await ctx.send(f"{member.mention} ist aktuell **Level {level}** ({total_xp} XP) und damit auf **Rang {rank}**. \nBis zum **nächsten Level** braucht {member.mention} noch {next_level_xp} XP.")

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

        leaderboard = sorted(data[guild_id].items(), key=lambda x: (self.get_total_xp_for_level(x[1]["level"]) + x[1]["xp"]), reverse=True)
        top_users = leaderboard[:10]

        leaderboard_text = "Leaderboard\n"
        for idx, (user_id, user_data) in enumerate(top_users, start=1):
            user = await self.bot.fetch_user(int(user_id))
            leaderboard_text += f"**#{idx}** {user.mention} - Level {user_data['level']} ({user_data['total_xp']} XP)\n"

        await ctx.send(leaderboard_text)

async def setup(bot):
    await bot.add_cog(LevelSys(bot))